# 13 · Wireframe delta — what the live portal draws vs what the wireframe draws

**Written 2026-09-05** by the orchestrating session, from a side-by-side image
inspection: the wireframe crops in `wireframes/` (and the blueprint pages the PO
opened) against screenshots of the running product on tenant `silver-creek-water1`.

⚠ **THIS IS AN IMAGE COMPARISON, NOT A SPEC COMPARISON.** `08-screen-layouts.md`
says which components a screen composes; this file says what is different when a
person looks at the two pictures. The two find different things — the spec pass
cannot see that a bold span covers the wrong clause, and this pass cannot see
that a component was composed correctly for the wrong reason. Both are needed and
neither replaces the other. The 50-screen spec audit is a separate lane.

⚠ **NINE SCREENS IN THE FIRST PASS; FIFTEEN AFTER THE WAVE-F PASS OF 2026-09-06 ADDED SIX (`CWP-020` `CWP-023` `CWP-024` `CWP-025` `CWP-065`, and a re-read of `CWP-022`) — see the second pass at the foot of this file.**

⚠ **NINE SCREENS, SEVEN WITH BOTH PICTURES.** `CWP-035` is unbuilt, so there is
nothing to compare it to; `CWP-040`'s live side was never opened. Every other
screen in the portal is uninspected by this pass and its absence here means
nothing.

⚠ **AMENDED 2026-09-06 — A SECOND PASS ADDED WAVE G's FIVE SCREENS, AND OPENED
`CWP-040`.** `CWP-027`, `CWP-028`, `CWP-029`, `CWP-031` and `CWP-041` are
compared at the foot of this file, and `CWP-038`, `CWP-039` and `CWP-040` gain
rows there. So the count is **fourteen screens**, and the sentence above is
true of the ORIGINAL pass only. Sixty-three of the seventy-seven wireframes are
still uninspected and their absence still means nothing.

⚠ **AMENDED AGAIN 2026-09-06 — A FOURTH PASS ADDED WAVES P AND R's FOUR SCREENS**
(`CWP-002`, `CWP-003`, `CWP-004` and a third row on `CWP-039`), at the foot of
this file. **Nineteen screens now carry rows.**

⚠ **AND THE RUNNING TOTAL IN THIS HEADER HAS BEEN WRONG IN TWO PLACES SINCE THE
MORNING, WHICH IS WORTH MORE THAN THE CORRECTION.** The wave-F line above says
*"FIFTEEN AFTER THE WAVE-F PASS OF 2026-09-06 ADDED SIX"*; the wave-G paragraph
directly beneath it says *"the count is **fourteen screens**"*. Both were
written the same day by different passes and neither is a lie — each counted
correctly from the state IT could see. **This is `CLAUDE.md`'s rule-count
lesson living in a second file:** ratifying a pass and updating the pointer to it
are two acts, only the first feels like the work, and a number maintained by
hand in a header drifts every single time. The count above is left standing with
this note beside it rather than quietly rewritten, because the pattern is the
finding. **If you need the number, count the `##` screen sections.**

⚠ **THREE ROWS OF THIS FILE WERE WRONG AND ARE CORRECTED IN PLACE — `DEF-CWP-3993`,
2026-09-05.** A lane sent to build `CWP-034` and `CWP-037` opened the two PNGs first,
as this file's own header asks, and found that 37.3 describes a coloured square the
image does not have, 37.7 puts a button on the right where the image puts it
underneath, and 34.2 calls a grey-on-outline button a brand primary. Two of the three
would have produced something the drawing does not contain. **The file is evidence and
not law, exactly as it says of itself — open the image beside it.** Each corrected row
is stamped inline rather than rewritten, so the original reading stays visible.

**Change types**, so a lane can take a slice rather than a screen:

| Type | Means |
|---|---|
| `STRUCTURE` | a panel, rail, column or section missing, or in the wrong place |
| `CONTROL` | a button or link missing, dead, or somewhere it does not belong |
| `COPY` | wording, or emphasis landing on the wrong clause |
| `DATA` | a raw system value, a seed value, or the wrong field entirely |
| `FORMAT` | dates, number grouping, letter case |

---

## ⚠ CONFIRMED INDEPENDENTLY, AND IT COLLAPSES TO SIX PIECES OF WORK

**Added 2026-09-05, after this file was written.** A separate lane opened all fifty
portal addresses in a browser and compared them against `08-screen-layouts.md` —
the SPEC, not the images — with no sight of this file. It reports its own headline
as *"almost everything on the list comes from three faults, not twenty-four"*, and
**its three are this file's cross-cutting section arrived at from the other
direction**:

| Their fault | This file's rows | What it actually is |
|---|---|---|
| The signed-in portal has **no page heads** | `X4` `X5` · 34.2 · 33.4 · 41.5 | One missing composition. It explains the missing heading AND **the missing top row of buttons** — which is where the drawing puts *Download all*, *Pay*, *Download CSV*, *Send a reading*. This file saw the symptoms one screen at a time and did not see they were one cause |
| **No list uses the shared table** | `X6` `X7` · 34.3 · 34.5 · 41.4 · 41.6–41.8 | Six lists with no search, no sort, no row icons, no footer |
| **`KpiRow`/`KpiTile` has never been built** | 22.1 · 33.1 | Home and Usage open with stacked boxes instead of a row of figures |

Their pass also found what an image comparison cannot: **`SegmentedChoice` writes
its label to `aria-label` only**, so four On/Off buttons on contact preferences
render unlabelled — one line of code, and it fixes Usage and Accounts at the same
time. And this file found what a spec comparison cannot: the three formatting
decisions (`X1` `X2` `X3`) and the emphasis landing on the wrong clause (34.7,
37.8, 39.4).

**So the seventy changes are six pieces of work:**

1. **A page head on the signed-in screens** — heading, one sentence, and the top action row
2. **The lists onto the shared table** — search, sort, row icons, footer
3. **Build `KpiRow` / `KpiTile`**
4. **Give the screens their right-hand column** (`X8`, and 22.6–22.8 are its contents)
5. **One formatter for dates, digit grouping and chip case** (`X1` `X2` `X3`)
6. **`SegmentedChoice`'s label** — one line, three screens

Everything else in this file is either a consequence of those six or a per-screen
copy fix. **`CWP-038`'s three findings are the exception and are not in that list**
— the invented gate, the sentence naming no method, and the dead end for a
customer with no saved card are that screen's own, and they are the ones that stop
a person paying.

⚠ **TWO THINGS THIS FILE OR ITS BRIEF GOT WRONG, corrected by that lane:** a
**corrected bill is on screen and reads correctly** — the superseded bill stays in
the list, greyed, saying *Replaced by …*, and its replacement says *Replaces …*;
only the colour differs. And the bill status words come from a shared five-value
map that already includes *Corrected*. Nobody should spend a wave on either.

Their full pass is `14-layout-audit.md`.

---

## Cross-cutting — fix once, and eight screens move

These are not per-screen defects. Each one is a single decision in the shared kit
or the shared formatter, and each is visible on most screens in this file.

| # | Type | What the wireframe does | What the product does |
|---|---|---|---|
| X1 | `FORMAT` | `31 Aug 2026`, `Mar 2021`, `12 Aug 2026` | `2026-08-14` everywhere — a raw computer date, on every screen, in every column. The regional date setting reaches nothing |
| X2 | `FORMAT` | `153,040` · `4,820 gal` · `48,120 gal` | `6462` · `1400 kWh` — no digit grouping anywhere, including the dial figure a customer checks against the box on the wall |
| X3 | `FORMAT` | Status chips read `IN SERVICE`, `CLEARED`, `DUE`, `BOUNCED` — **uppercase, letter-spaced** | `Installed/Active`, `Cleared` — sentence case, and sometimes the raw stored value |
| X4 | `STRUCTURE` | Page title is **large, sentence case, dark** under a small uppercase kicker (`USAGE` → *What you have used*) | The title IS the kicker: `METERS AND EQUIPMENT`, `YOUR PAYMENTS`, `READINGS ON YOUR METER` — small, uppercase, grey. The page has no heading, only a section label |
| X5 | `CONTROL` | Back is a text link, `← USAGE`, above the title | A bordered button captioned `Back to usage`, sitting where a primary action would sit |
| X6 | `CONTROL` | Every table row ends in icons — 👁 view, ✎ edit, 🖨 receipt, − remove | No row icons on any table in the portal. B14 rule 15 reserves icons for exactly this |
| X7 | `STRUCTURE` | Tables end in a footer: `Showing 1–5 of 31` left, `← ← Page 1 of 7 → →` right | No footer, no count, no pagination, on any portal table |
| X8 | `STRUCTURE` | Right rail carries the standing facts (`YOUR SERVICE`, `WHERE IT WILL GO`, `NEXT FEW`) | No right rail on any signed-in screen. Everything is one column of stacked cards |

---

## `CWP-022` · Portal home (wireframe P8)

The live screen is a vertical stack of cards. The wireframe is a four-tile strip
over a two-column body. **A lane is rebuilding this now** — listed for completeness
and because the tile figures below are the acceptance detail.

| # | Type | Change |
|---|---|---|
| 22.1 | `STRUCTURE` | Four KPI tiles across the top: `BALANCE` (with a brand left rule) · `LAST BILL` · `LAST PAYMENT` · `WATER THIS MONTH`. Each is a label, one big figure, one grey line under it — `$142.18` / *Due 14 Sep · in 12 days* |
| 22.2 | `STRUCTURE` | Two columns beneath: main ⅔, rail ⅓ |
| 22.3 | `STRUCTURE` | Main column: `NEEDS YOUR ATTENTION` panel with a `View all` link, then `RECENT BILLS` with an `All bills →` link |
| 22.4 | `STRUCTURE` | `NEEDS YOUR ATTENTION` rows are chip + sentence + button: amber `DUE SOON` · *Bill BL-2608-0141 is due on 14 September.* · `Pay $142.18`; grey `READING` · *Your water reading is due between 2 and 6 September.* · `Send a reading` |
| 22.5 | `COPY` | A panel with nothing in it **renders as nothing** — never an empty box saying "no items" |
| 22.6 | `STRUCTURE` | Rail: `TWELVE MONTHS OF WATER` sparkline with a `Usage →` link and the caption *Gallons per month. August is your highest.* |
| 22.7 | `STRUCTURE` | Rail: `YOUR SERVICE` — Address / Plan / Billed / Paperless as a label-left value-right list with hairline rules |
| 22.8 | `STRUCTURE` | Rail: `PAYING BY INSTALMENTS?` — two-line prompt + `Ask for a plan` button |
| 22.9 | `STRUCTURE` | `RECENT BILLS` columns: BILL / PERIOD / USAGE / AMOUNT / STATUS, with usage right-aligned as `4,820 gal` and a chip in STATUS |

---

## `CWP-033` · Usage (wireframe P19)

Live shows one card per service and the words *No readings yet on this service.*
on both metered services, while the same account's bill prices 1,500 kWh and
16 kgal. **The empty chart is a data-wiring fault with its own lane** (nothing
recomputes monthly usage when a reading is committed). The layout gaps below are
separate and stand whether or not the data arrives.

| # | Type | Change |
|---|---|---|
| 33.1 | `STRUCTURE` | Three KPI tiles under the page head: `WATER · THIS PERIOD` **4,820** gal / *18% above last August* · `DAILY AVERAGE` **155** gal / *Household of three: typical* · `NEXT READING DUE` **2–6** Sep / *Send your own, or we will call*. The unit sits small beside the figure, not inside it |
| 33.2 | `STRUCTURE` | A chart panel: `WATER · GALLONS PER MONTH`, twelve bars, month initials on the axis, and a brand-coloured note on the right of the panel head — *Sewer is billed on this figure* |
| 33.3 | `STRUCTURE` | A legend strip under the chart: `Measured` · `Highest month` · *Lowest 3,050 gal · highest 4,820 gal* |
| 33.4 | `CONTROL` | Segmented `12 months` \| `24 months` and `↓ CSV`, on the page head line, right — live has these but as two loose buttons plus a download icon |
| 33.5 | `STRUCTURE` | Three per-service cards in a row of three: WATER (This year `48,120 gal` / Last year `44,900 gal`) · SEWER (Billed on **Water used** / Not separately metered `—`) · TRASH (Billed on **Your 96 gal cart** / Not measured `—`). Live stacks six full-width cards |
| 33.6 | `COPY` | An unmeasured service shows **no chart** and says why — that is the design, not a gap |
| 33.7 | `DATA` | Live prints *No readings yet on this service* on ELECTRIC and WATER while readings exist. Wireframe expects figures |

---

## `CWP-034` · Every reading (wireframe P20)

| # | Type | Change |
|---|---|---|
| 34.1 | `STRUCTURE` | The screen is scoped to **one meter** — title *Readings on your water meter*, context `water · front meter`. Live puts every meter in one table, so electric `6462` and water `2007` sit on the same date with nothing saying which is which. Either scope the screen with a meter chooser or add a meter column; today a customer cannot tell the rows apart except by the unit |
| 34.2 | `CONTROL` | ⚠ **CORRECTED 2026-09-05 AGAINST THE IMAGE (`DEF-CWP-3993`) — IT IS NOT A PRIMARY.** `CWP-034.png` draws `Send a reading` top right as an **OUTLINE button with a brand border and GREY text**, which is this kit's held presentation. So the drawing already shows it held, and this row's instruction to ship it held was right for a reason it did not notice. Built 2026-09-05: `HeldButton` in `PageHeader`'s action slot, reason *Sending readings is not ready yet*, with the two cases that go red the day `CWP-035` gets an address or a register row |
| 34.3 | `CONTROL` | `TAKEN ⇅` carries a sort affordance |
| 34.4 | `COPY` | *How it was taken* is **plain text** — `Read by a meter reader`. The chip is reserved for the one row that differs: amber `ESTIMATED` followed by plain *then corrected*. Live puts a grey chip on every row, which spends the emphasis that was meant to mark the exception |
| 34.5 | `STRUCTURE` | Table footer — `Showing 1–4 of 26` + pagination |
| 34.6 | `CONTROL` | Row icons 👁 ✎ at the right edge |
| 34.7 | `COPY` | The notice bolds the word **estimated** inside the first sentence. Live bolds the whole second sentence instead, so the definition being offered is not the thing emphasised |
| 34.8 | `FORMAT` | `31 Aug 2026` · `153,040` · `4,820 gal` (see X1, X2) |
| 34.9 | `STRUCTURE` | Back link and page title (see X4, X5) |

---

## `CWP-035` · Send your own reading (wireframe P21) — **not built**

Nothing to compare. Recorded here because `CWP-034`'s held button points at it and
because the wireframe is specific enough to build from:

kicker `READINGS` · title *Send us your reading* · subtitle *The window for your
route is open until 6 September.* → main card [ `Which meter` select showing
*Water · front · serial 88-40219* · `Date you read it *` · **the dial input** — wide,
letter-spaced digits, in a **flagged** state with a brand border and the sentence
*That is 5,900 gallons in two days — about nineteen times your usual. Check the
dials and try again, or send it anyway and we will look.* · `A photo of the meter`
picker, *Optional, but it settles most questions* · `Send it ✓` primary + `Cancel` ]
→ rail [ `LAST READING` — Taken 31 Aug / **153,040**, Expected now / **about 153,300**
· `WHAT HAPPENS TO IT` — three checklist rows: **You send it** *held, not billed yet* /
**We check it** *same rules as our own readers* / **It goes on your next bill** *or we
ring you if it looks odd* ].

---

## `CWP-037` · Meters and equipment (wireframe P23)

| # | Type | Change |
|---|---|---|
| 37.1 | `COPY` | Title *What is installed at your property*. Live reads `METERS AND EQUIPMENT` |
| 37.2 | `DATA` | Equipment named for what it is — `Water meter`, `Refuse cart`, `Backflow device`. Live prints `Meter` on both rows, so two rows read identically and only the serial separates them |
| 37.3 | `STRUCTURE` | ⚠ **WITHDRAWN 2026-09-05 — THERE IS NO SQUARE (`DEF-CWP-3993`).** `CWP-037.png` was re-opened and cropped at 2x: the equipment names are indented from the column edge and nothing precedes them. Do not build this. The service DOES belong in that cell, but as the equipment's NAME — see 37.2 |
| 37.4 | `DATA` | `WHERE` is filled — *Front boundary box*, *Rear alley*. Live shows `—` on every row. Establish whether the location is missing from the payload or from the data; those are different faults |
| 37.5 | `FORMAT` | `FITTED` is month + year — `Mar 2021`, not a full date and not ISO |
| 37.6 | `DATA` | `STATUS` reads `IN SERVICE` / `TEST DUE NOV`. Live prints `Installed/Active` — a stored value with a slash in it, on a customer's screen. ⚠ **AND THE IMAGE SHOWS EXACTLY ONE CHIP PER ROW**, which this row does not say: the test-due row does NOT also say `IN SERVICE`, where live stacked both. Built 2026-09-05 as *the test chip replaces the state chip when the state is in-service, and both show when it is not* — following the drawing literally would have hidden *needs repair* behind *test due Nov*. The four behaviour classes travel and the catalogue writes the word (`DEF-CWP-3992`) |
| 37.7 | `CONTROL` | The notice carries a `Report a problem` button. Absent. ⚠ **CORRECTED 2026-09-05: NOT *on its right* (`DEF-CWP-3993`).** The image puts it on its OWN LINE BENEATH the sentence, left-aligned and indented past the `i`, inside the same bordered box. `InfoBar` gained a `below` slot for it rather than reusing `trailing`, which is the right-hand one. `/report` is `CWP-006` and is BUILT, so this is a live door and not a hold |
| 37.8 | `COPY` | The notice bolds **Tell us rather than touching it**. Live bolds *the meter belongs to the utility* — the reassurance rather than the instruction |
| 37.9 | `COPY` | Wireframe opens *Something damaged, buried or leaking?*; live drops the first word |

---

## `CWP-038` · Pay now (wireframe P24)

The most consequential of the nine: this screen takes money, and as it stands a
customer with no saved method cannot complete it at all.

| # | Type | Change |
|---|---|---|
| 38.1 | `CONTROL` | ✅ **BUILT 2026-09-05 (2.169.3, `DEF-CWP-3970`).** The control is deleted and the preview is a debounced effect, so the panel is on screen the moment the page opens. **Delete `Show me where it goes`.** `WHERE IT WILL GO` is a standing right-rail panel, visible before the customer commits. The blueprint's own note says it is not decoration: payments are allocated by a rule the utility configures, so someone paying part of a balance has to see which bill it lands on *first*. Hiding it behind a button defeats the only reason it exists |
| 38.2 | `STRUCTURE` | ✅ **BUILT 2026-09-05.** `WHAT THIS WILL DO` sits **inside the left card**, under the payment method — not in the rail |
| 38.3 | `DATA` | ✅ **BUILT 2026-09-05 (`DEF-CWP-3971`).** The bullet is not written at all when nothing is chosen. The first bullet rendered as *"Takes $155.45 from **.**"* — the sentence names no method and ends in a bare full stop. With no method chosen the bullet must not be written at all |
| 38.4 | `CONTROL` | ✅ **BUILT 2026-09-05 (`DEF-CWP-3972`).** The third radio is drawn always and PRE-SELECTED when nothing is saved, with a live link to `/payment-methods` behind it. Was: no way to pay. `HOW YOU ARE PAYING` is an empty state — *Cards and bank accounts you save will show here* — and the wireframe's third option, **`A different card or bank account`**, is missing. Without it the screen is a dead end for every customer who has not already saved an instrument |
| 38.5 | `CONTROL` | ✅ **BUILT 2026-09-05.** `Pay $155.45 ✓` and `Back` belong in a button row at the **bottom left of the card**. Live floats the pay button outside the card, top right, and has no `Back` at all |
| 38.6 | `COPY` | ⏳ **LEFT TO THE KIT LANE 2026-09-05, AND THE HUNK IS WRITTEN OUT SO IT COSTS SECONDS.** `RadioList` in `portal/components/primitives.tsx` types its option label as `label: string`, so a screen cannot put a `<strong>` inside one without hand-rolling a second radio (B14 rule 36 forbids that) — and `primitives.tsx` is the kit lane's file with uncommitted edits in it, where a second author is how hard-won law 11's DEF-165 happened. **The change is two lines: widen `label: string` to `label: ReactNode` on the options type, and the render already interpolates `{option.label}` unchanged.** Then this screen passes `<>The whole balance — <strong>$142.18</strong></>`. The money inside each amount option is **bold** — *The whole balance — **$142.18*** |
| 38.7 | `COPY` | ⏳ **NOT DONE 2026-09-05 AND IT IS NOT A COPY EDIT.** *Just the August bill* names a MONTH; the screen has `bills[0].number` and no month, so the wording change needs `issued_on` (which the payload already carries) turned into a month name through the shared date formatter the kit lane is building — writing a second one here is the thing that lane exists to stop. Option wording: *The whole balance* / *Just the August bill* — live reads *Everything you owe* / *Just bill BL-2608-000077*, which puts a bill number where the wireframe puts a month |
| 38.8 | `STRUCTURE` | A saved method carries its own status chip — green `VERIFIED` beside the bank account |
| 38.9 | `STRUCTURE` | ✅ **DIVERGENCE RECORDED AND KEPT 2026-09-05.** Both are still there and both are deliberate: `LEFT OWING` is `US-CWP-045` TC-4's own acceptance sentence (*"afterwards that bill reads owing $102.18"*), which a customer who can only see it AFTERWARDS has been told at the one moment they cannot act on it; and `You are paying` is the total a partial payment is checked against. **The drawing is not violated — it is exceeded, on purpose, and this row is the record.** Live's rail table adds a fourth column `LEFT OWING` and a `You are paying` total that the wireframe does not have. Both are improvements — keep them, and record the divergence so the wireframe is not treated as violated |

---

## `CWP-039` · Your payment methods (wireframe P25)

| # | Type | Change |
|---|---|---|
| 39.1 | `COPY` | ✅ **BUILT 2026-09-05 (2.169.4).** Kicker `PAYMENTS`, title *Cards and bank accounts*. Live reads kicker `PAYING`, title *Your payment methods* |
| 39.2 | `CONTROL` | ✅ **BUILT 2026-09-05 (`DEF-CWP-3973`), AND THIS ROW IS HALF WRONG — SAME CORRECTION AS 34.2 (`DEF-CWP-3993`).** `CWP-039.png` cropped at 4x draws `+ Add a method` **brand-bordered with GREY text**, which is this kit's HELD presentation, not a solid primary. **The drawing is right about the shape and out of date about the state:** it was drawn when the stored-instrument table did not exist (its own note — *"Rests on: nothing — the stored-instrument table … was never created"*), and `POST /portal/payment-methods` writes one today. So it ships LIVE in the drawn POSITION — a held control over a working path is `DEF-CWP-3925`, which this product has paid for eight times. `+ Add a method` is a **brand primary button beside the title**. Live buries it inside an information notice, which is the one place a primary action should never be |
| 39.3 | `STRUCTURE` | ✅ **BUILT 2026-09-05.** Verified in a browser: `Chase ••••4021` over grey *Bank account*, `Visa ••••8812` over grey *Card · expires 11/27*, chips `VERIFIED` / `ACTIVE`, and ✎ − at the row's end — the pencil HELD with *Changing one is not ready.*, because there is no edit endpoint and `CR-068` R3 asks a control that may not be used to be visible and say why. When methods exist, a table: `METHOD` (two lines — **Chase ••••4021** over grey *Bank account*) / `ADDED` / `USED FOR` (*Autopay · one-off payments*) / `STATUS` chip / row icons ✎ − |
| 39.4 | `COPY` | The notice bolds **Your bank or card company holds it and gives us a token**; live shortens the sentence and bolds a different span |
| 39.5 | `CONTROL` | ✅ **BUILT 2026-09-05, AND THE ROOT CAUSE IS NOT WHAT THIS ROW GUESSES.** The control was never given a width: `Card` is `flex flex-col`, so a control placed DIRECTLY in it stretches to the card — every correctly-sized control in this portal sits inside a `flex` row and this one did not. Measured in a browser: **1060px before, 121px after.** The class list is identical either way, which is why nothing could see it. ⚠ **AND THE DOOR STAYS LIVE.** `CWP-040` is built and routed; holding a door over a live screen is `DEF-CWP-3925`. What cannot happen is the CHARGE, so the standing is now SAID on this card — *Autopay cannot be switched on yet.* — instead of being discovered on the next screen. `Set up autopay` renders as a full-width bordered button that looks live. Autopay is **blocked** — the wireframe's own words: *Today this switch would be a promise nobody can keep.* The held state has to be visible, and a full-width button is not one of the kit's two button sizes |
| 39.6 | `STRUCTURE` | ✅ **DIVERGENCE RECORDED AND KEPT 2026-09-05.** Both cards stay: `AUTOPAY` now carries one sentence of standing plus a correctly-sized door, and `CARD FEES` states the tenant's stance with no figure (`OQ-1394`). The `AUTOPAY` and `CARD FEES` cards are ours, not the wireframe's, which gives autopay its own screen. Keep them as a summary if they earn it — but record the divergence rather than leaving it to look like drift |

---

## `CWP-040` · Autopay (wireframe P26) — live side not inspected

Recorded so the next pass knows what to open it against: kicker `PAYMENTS` · title
*Pay automatically each month* → card [ `Take it from` select · `How much` select
with helper *Or set a ceiling and we will ring you above it.* · `When` — a
**read-only** field reading *On the due date*, helper *Always the due date. It
cannot be changed.* · `WHAT THIS WILL DO` panel with the brand left rule ·
`Turn autopay on`, greyed ] → rail [ `NEXT FEW` — DATE / EXPECTED / STATUS with
`14 Sep 2026 · $142.18 · SCHEDULED` and `14 Oct 2026 · — · NOT BILLED YET` · a
red-bordered panel carrying the promise-nobody-can-keep sentence ].

---

## `CWP-041` · What you have paid (wireframe P27)

| # | Type | Change |
|---|---|---|
| 41.1 | `COPY` | ✅ **BUILT 2026-09-05 (2.172.1).** `components/PageHeader` composed — no second page head was built. Kicker `PAYMENTS`, title *What you have paid*. Live reads `YOUR PAYMENTS` |
| 41.2 | `DATA` | ✅ **BUILT 2026-09-05 (2.172.1, `DEF-CWP-3974`), AND IT WAS TWO FAULTS RATHER THAN ONE.** (a) The FIXTURE wrote a bill number into the cheque-number column — `confirmation=f"SAMPLE-{invoice.invoice_no}"` — and two more rows wrote `SAMPLE-PLAN-<the plan's UUID>`, **a database id on a customer's screen, B14 rule 31, from the fixture rather than from the screen.** Each tender now seeds the reference that tender really produces: a cheque number, `Chase ••••4021` on ACH, `Visa ••••8812` on card, and NOTHING on cash. (b) The SEAM printed it verbatim, so a bare `10188` read as a quantity; the tender now decides the shape once, server-side — `#10188` — and the browser holds no second definition. ⚠ **A TENANT SEEDED BEFORE TODAY KEEPS `SAMPLE-…` UNTIL IT IS SEEDED AGAIN** (hard-won law 4's shape for data). `REFERENCE` is what the customer would recognise — `Chase ••••4021`, `#10188`, `Visa ••••8812`. Live prints `SAMPLE-BL-2608-000077`: the internal confirmation field, carrying a seed prefix, on a customer's screen |
| 41.3 | `STRUCTURE` | ✅ **BUILT 2026-09-05.** The two rows were right; only the CHIP was red, so date, how, reference and the amount all read exactly like a payment that went through. Every cell of the reversal is `text-danger-700` now and the row beneath it is not — both halves asserted, because a test that only counted red cells would pass on a screen that painted both rows. ⚠ **PER CELL AND NOT PER ROW:** `PortalListTable` takes `rowMuted` and no tone, and the shared table is another lane's file this week (law 11 / `DEF-165`). If a `rowTone` lands, this collapses to one prop and the test still asserts the right thing. **A bounced payment is two rows and the reversal is drawn in red** — its date, method, reference and the words *Returned by the bank* in the applied-to cell, over a negative amount `−$129.02` and a red `BOUNCED` chip. The row it undoes sits directly beneath with a grey `REVERSED` chip. Nothing in the product edits a payment, so the customer sees both, and the wording has to carry it |
| 41.4 | `STRUCTURE` | A toolbar inside the table card: `Search payments…` · `All` \| `This year` · `▦ Columns` on the right |
| 41.5 | `CONTROL` | ⏳ **NOT THIS LANE'S — the page head now EXISTS to hold it** (41.1, built today). `↓ CSV` is an outline button **on the title line**. Live has it at the bottom of the card, greyed, as `Download CSV` |
| 41.6 | `CONTROL` | Row icons — 👁 on every row, a receipt icon on the ones that have one. The bounced row correctly has only the eye |
| 41.7 | `STRUCTURE` | Footer: `Showing 1–5 of 31` + pagination |
| 41.8 | `CONTROL` | `DATE ⇅` sorts |
| 41.9 | `STRUCTURE` | ✅ **BUILT 2026-09-05 (2.172.1, `DEF-CWP-3975`).** The same seven destinations and the same by-address assertion, as `ErrandCard`s in a `CardGrid3` — title, one grey line saying what the errand IS, `Start →`. The descriptions are the point: seven boxes reading *Your payment plan · A plan we have offered you · Credits on the account* asked a customer to tell three near-identical phrases apart from four words each. **The seven bare buttons at the foot are not in the wireframe and are not a design.** *Pay a bill · Your payment methods · Automatic payment · Your payment plan · A plan we have offered you · Credits on the account · What starting service will cost* — a wrapped row of undifferentiated boxes. These are errands and belong in the shared errand-card grid the home page already uses: title, one grey line, `Start →` |
| 41.10 | `FORMAT` | The selected segment is painted **blue**. Nothing else in this product is blue; the brand is the red the wireframe uses throughout. Ties to the open defect that the portal reads no brand colour at all |

---

## What this pass could not see

* **Eight of the nine screens were opened on one tenant, one account, one width.**
  Nothing here says anything about a phone, a long utility name, a customer with
  four accounts, or a service the tenant does not offer.
* **Colour and spacing were judged by eye from a screenshot.** Where a change says
  *brand colour* or *uppercase*, the token is the authority, not this file.
* **`CWP-040` and the other 68 portal screens are uninspected.** Their absence from
  this file is not a clean bill.

---

# Second pass — CR-068 **wave F**, 2026-09-06

**Six more screens, taking this file from nine to fifteen of seventy-seven.**
Added by the wave-F walkthrough lane, the same way the first pass was made: the
saved PNG in `wireframes/` open beside the running product, on tenant
`pine-hill`, seeded by `seed_portal_demo` + `def-cwp-3965-fixture.py`, at
1440×1000. **Both logins were walked** — a householder with one account and a
landlord with three — because half of what is below is only visible on one of
them.

⚠ **AND THE SAME CAUTION THIS FILE OPENS WITH APPLIES TO THE ROWS BELOW.** Three
rows of the first pass were wrong (`DEF-CWP-3993`) and two of the three would
have produced something the drawing does not contain. **Everything here was read
off the image, and then off the running screen, and the ones that were CLOSED
were re-read off the screen afterwards.** Where a row says `CLOSED` it means a
person looked at the pixels after the fix, not that a test went green.

⚠ **ONE THING THE FIRST PASS COULD NOT HAVE SEEN AND THIS ONE ALMOST GOT WRONG.**
`CWP-022`'s usage tile reads `10700kWh` in `innerText` and looks like a missing
space. It is not: the unit is its own `<span>` with a left margin, and the
browser paints the gap. **Reading `innerText` of a parent glues two spans
together and reading the child separates them, and neither is what the customer
sees** — the only way to settle it is to look at the rendered page. A defect was
nearly filed for it. The grouping, `10700` for `10,700`, was real and is
`DEF-CWP-4140`.

## `CWP-022` · Portal home (wireframe P8) — **re-read 2026-09-06**

The first pass listed 22.1–22.9 while a lane was rebuilding this screen. That
rebuild landed (`DEF-CWP-3965`), so every structural row above is now **CLOSED**:
the four-tile strip, the two columns, both main panels, the three rail panels and
the recent-bills columns are all on the screen. What was still wrong on
2026-09-06, found by reading the same image again:

| # | Type | Change | State |
|---|---|---|---|
| 22.10 | `FORMAT` | Dates are printed as machine values: `Issued 2026-08-02`, `Paid 2026-08-09`, period `2026-07-01 – 2026-07-31`. The drawing writes *Issued 30 Aug*, *12 Aug · Bank transfer*, *1–31 Aug* | **CLOSED** `DEF-CWP-4131` — one `onDate` in the kit; now *Issued Aug 2, 2026* |
| 22.11 | `FORMAT` | The usage tile prints `10700`; the drawing writes `4,820` | **CLOSED** `DEF-CWP-4140` — composes the kit's `formatQuantity`; now `10,700` |
| 22.12 | `COPY` | **Only visible on a landlord.** The *what this figure leaves out* line is printed once per account — three identical sentences in a row under one figure | **CLOSED** `DEF-CWP-4132` — said once |
| 22.13 | `CONTROL` | The header has **no Messages bell**; the drawing puts `Messages ²` left of `Help` | **OPEN** — the shell is wave E's, not this wave's. Recorded, not filed |
| 22.14 | `COPY` | The lead tile's second line reads *across 3 accounts* for a landlord and the drawing writes *Due 14 Sep · in 12 days* | **NOT A GAP** — a set of three accounts has three due dates. The householder's tile draws the date and the countdown, which is the state the drawing is of |

## `CWP-023` · All my accounts (wireframe P9)

The live screen is close to the drawing — a real toolbar, real sort carets, a
real footer. What is missing is at the two ends of every row.

| # | Type | Change | State |
|---|---|---|---|
| 23.1 | `CONTROL` | **No row actions at all.** The drawing puts two icons on every row and its own caption insists on the shape: *"Note the row actions are icons, not links: view and pay, with anything rarer behind an overflow"*. The table ended at the STATUS chip | **CLOSED** `DEF-CWP-4133` — 👁 to that account's bills, a money glyph to pay, both setting the current account rather than putting an id in an address |
| 23.2 | `FORMAT` | NEXT DUE prints `2026-08-22`; the drawing writes `14 Sep` | **CLOSED** `DEF-CWP-4131` |
| 23.3 | `COPY` | The same *leaves out* sentence three times, as on home | **CLOSED** `DEF-CWP-4132` |
| 23.4 | `COPY` | Title reads *All my accounts*; the drawing writes *Four accounts on this login* — a counted sentence | **OPEN** — a counted title needs a plural frame in eleven catalogues, written natively (B14 rule 35). Recorded rather than machine-translated |
| 23.5 | `CONTROL` | The drawing's head carries two actions, `+ Add an account` and `Pay several →`. The screen offers *Add another account* without the `+` (r10 rule 4: `+ Noun` opens a creator) and no *Pay several* | **PART OPEN** — the file's own comment says *Pay several* has no address in the product and a held button pointing at nothing is what `DEF-CWP-3925` cost a week. That reasoning is right and is left alone. The missing `+` is copy, unfixed |
| 23.6 | `STRUCTURE` | The drawing right-aligns **Total owing** on the toolbar row; the screen puts it on its own line above the search | **OPEN** — layout, not correctness |
| 23.7 | `CONTROL` | Filter chips are `All | Owing`; the drawing has `All | Owing | On a plan` | **OPEN** — a plan filter needs a plan flag on the row, which the payload does not carry |
| 23.8 | `COPY` | Column head reads `ADDRESS`; the drawing writes `SERVICE ADDRESS`. Status chip reads `15 DAYS OVERDUE`; the drawing writes `OVERDUE 19 DAYS` | **OPEN** — wording only, and the second is arguably clearer as built |
| 23.9 | `COPY` | Footer reads `1–3 of 3`; r10 rule 16 and the drawing write `Showing 1–4 of 4` | **OPEN** — the pager is the shared kit's, so this is a kit change affecting every list in the product, not a portal one |

## `CWP-020` · Add another account (wireframe P6)

The form is right — both fields marked required, and the consequence box the
drawing draws, in the right place, before the commit (r10 rule 11).

| # | Type | Change | State |
|---|---|---|---|
| 20.1 | `DATA` | The rail lists the **account number** beside each address; the drawing lists the **balance** (`$142.18`, `$0.00`, `$318.04`, `$412.60`). The rail was answering the question the form on the left is already asking | **CLOSED** `DEF-CWP-4138` |
| 20.2 | `COPY` | The commit reads *Find this account*; the drawing writes *Add account ✓*. r10 rule 4 makes these different acts — `Verb ✓` commits, `Verb →` advances — and this control advances to a code step | **OPEN** — the screen is a two-step flow the drawing renders as one, so neither label is simply right. Recorded rather than guessed |
| 20.3 | `COPY` | Title reads *Add another account*; the drawing writes *Add an account to this login*. Panel head reads *WHAT HAPPENS WHEN YOU ADD IT*; the drawing writes *WHAT THIS WILL DO* | **OPEN** — wording, and both say the same thing |

## `CWP-024` · My details (wireframe P10)

| # | Type | Change | State |
|---|---|---|---|
| 24.1 | `CONTROL` | The SIGN-IN panel states three facts and offers **neither of its two controls**. The drawing puts a `ButtonRow` beneath it with *Change password* and *Sign out everywhere*. `POST sessions/revoke-all` shipped in wave E and nothing points at it | **OPEN** `DEF-CWP-4362` — both are new controls on a security path and each needs a destination ruling. Hard-won law 2 in its second direction. ⚠ **THIS ROW CITED `DEF-CWP-4137` UNTIL 2026-09-07 AND THAT IS A DIFFERENT, FIXED DEFECT** (the `CWP-063` plan-ends copy, closed in `873ee0a5`), so a lane following the id read a closed row and concluded the two controls were built. `G106` cannot see it twice over: it reads source code and not `12-governance/` prose, and the id it would look up DOES exist. |
| 24.2 | `COPY` | The commit reads *Save changes*; the drawing and r10 rule 4 write *Save changes ✓* — and *Save language ✓* one screen over already had it | **CLOSED** `DEF-CWP-4134`, all eleven catalogues |
| 24.3 | `FORMAT` | *Password changed 2026-09-06*; the drawing writes *Changed 4 Mar 2026* | **CLOSED** `DEF-CWP-4131` |
| 24.4 | `DATA` | *Codes go to* reads *Your mobile*; the drawing shows the masked number, `Text · ••• ••• 4218` | **OPEN** — the masked value exists in wave E's enrolment screen, so this is a read the panel does not make. Small and real |
| 24.5 | `COPY` | Title reads *My details*; the drawing writes *Your details* | **OPEN** — wording |
| 24.6 | `STRUCTURE` | The drawing puts a warning callout under the SIGN-IN panel (*a change of name or of who the account belongs to is **not** a form here*). The screen says the same thing in a *NOT CHANGED HERE* panel in the main column | **NOT A GAP** — same content, different column; the screen's placement is arguably better since it sits beside the fields it is about |

## `CWP-025` · How we contact you (wireframe P11)

| # | Type | Change | State |
|---|---|---|---|
| 25.1 | `STRUCTURE` | The row set differs: the screen lists Confirmations / Your bill / Moving in and out / Notices / Payment received / Payment plan letters; the drawing lists Your bill / Payment received / Payment overdue / Instalment coming up / Usage looks high / Planned works near you, and gives the last two `—` in POST rather than `ALWAYS` | **OPEN and ALREADY KNOWN** — `OQ-CWP-1660`, open. The drawing is 48 cells and the product holds three facts. Not this lane's to close |
| 25.2 | `CONTROL` | On/Off are drawn as a pair of bordered word-buttons rather than as a control | **OPEN** — named in B14 rule 36's own list of live breaches, and the layout-audit lane found the deeper half (`SegmentedChoice` writes its label to `aria-label` only). Left to that lane rather than fixed twice |
| 25.3 | `COPY` | *11 languages available.*; the drawing writes *Eleven languages available.* | **OPEN** — trivial, and in eleven catalogues |
| 25.4 | `DATA` | The PAPER panel shows *You have not been asked about paperless billing* | **NOT A GAP** — `BR-CWP-087` R6: existing customers are not asked. The fixture's account has no consent, so the consent-with-date state and the withdraw control could not be seen at all. **Stated so nobody reads this row as a clean bill** |

## `CWP-065` · Your account (wireframe P51)

The largest gap of the six, and the only screen where a whole column of the
drawing is absent end to end.

| # | Type | Change | State |
|---|---|---|---|
| 65.1 | `STRUCTURE` | **No heading of any kind** — the screen opened straight into YOUR SERVICES. The drawing has kicker `MY DETAILS`, title *Your account* and the sentence *The facts about this account that are not on a bill.* | **CLOSED** `DEF-CWP-4135` for the kicker and title. **The sentence is still missing** — minting it means writing it natively in eleven catalogues (B14 rule 35), which is not a thing to guess at |
| 65.2 | `STRUCTURE` | **YOUR SERVICES is a key-value list where the drawing is a three-column table** — SERVICE / ON SINCE / **BILLED ON** — and the third column is absent from the payload as well (`AccountSummary.services` is `{code, name, since}`). The drawing fills it with `Meter`, `Share of water`, `96 gal cart`, which is the one thing on this screen a customer cannot get from a bill | **OPEN** `DEF-CWP-4136` — the billing basis is rating knowledge and the portal does no rating (`CR-068` §2d). A backend story, sized on the row |
| 65.3 | `FORMAT` | `Since 2026-06-01` on every service and on the plan; the drawing writes `4 Mar 2021` and `1 January 2026` | **CLOSED** `DEF-CWP-4131` |
| 65.4 | `STRUCTURE` | The DEPOSIT panel and the TAX panel are both absent | **NOT A GAP, AND WORTH SAYING WHY** — the fixture's account holds no deposit and no exemption, and `US-CWP-031` TC-8 requires the panel to be ABSENT rather than `$0.00`. The walkthrough asserts this as a CORRESPONDENCE with the wire (`deposit === null` ⇒ zero panels) rather than as a constant, so it still fails if a real deposit stops being drawn |
| 65.5 | `STRUCTURE` | `HOW YOU ARE BILLED` shows only the current plan; the drawing adds *On this plan since* and *Before that* | **NOT A GAP HERE** — `billing.before` is `[]` on this fixture. The rows exist in the payload and the screen draws them when there is history (its own DOM test covers it) |
| 65.6 | `STRUCTURE` | The drawing's THIS ACCOUNT panel carries *Opened … · moved in* and *Transferred from 91 Cedar Row*; the screen carries *Opened* only | **OPEN** — the move record exists per the drawing's own footnote; the payload does not carry it |

## What this pass could not see

* **No deposit, no tax exemption, no paperless consent and no plan history were
  in the fixture**, so four panels were only ever seen in their absent state.
  Their rows above say so rather than reporting a pass.
* **`CWP-025`'s withdraw path was never exercised** — no consent exists to
  withdraw. The demo script's step 6 asks for it and this pass cannot answer it.
* **One tenant, one width, two logins.** Nothing here says anything about a
  phone, a long utility name, or a service the tenant does not offer.
* **The other sixty-two portal screens remain uninspected.** Fifteen of
  seventy-seven is where this file now stands, and the absence of a screen from
  it is not a clean bill.

---

# Wave G's five screens, added 2026-09-06

**Measured** by the CR-068 wave G lane against tenant `pine-hill` on a freshly
seeded clone, signed in as the LANDLORD (`maria@example.test`) — three accounts,
six bills in four states, six payments including a planted bounce. Screenshots
and a structural probe of each screen were taken with the running product and
compared against `wireframes/<SCREEN-ID>.png` opened beside them.

⚠ **THE ROWS ABOVE COVERED NINE SCREENS AND NONE OF THESE FIVE.** `CWP-027`,
`CWP-028`, `CWP-029`, `CWP-031` and `CWP-041`'s table rows are new here;
`CWP-038`, `CWP-039` and `CWP-040` already had sections and gain one row each.

⚠ **WHAT THE THREE SOURCES EACH DECIDED, because it changed several verdicts.**
B14 rule 36: the wireframe gives **layout and detail**, `r10`'s `UI-RULES.md`
gives the **visual style**, and the shared kit is how you comply. So a drawing
showing a button did not license picking its colour or grammar — r10 rule 4
(`+ Noun` creates, `Verb →` navigates, `Verb ✓` commits), rule 5 (two sizes),
rule 15 (row actions are ICONS, never text links) and rule 16 (a footer on every
list table) settled those. B14 wins on the one divergence that came up:
descriptions at **80%**, not r10's 66%.

⚠ **AND ONE THING THIS PASS EXPECTED TO FIND BROKEN AND DID NOT.** The layout
audit of 2026-09-05 records *"`CWP-029` — **No preview.** The drawing shows the
printed page; the screen is one sentence and a download link."* **That is fixed**
(`DEF-CWP-3983`): the screen composes `DocumentPreview` and frames the issued
file. Nobody should spend a wave on it.

⚠ **AND ONE THING THAT LOOKED BROKEN AND IS NOT — SETTLED 2026-09-06, NOT MERELY
SUSPECTED.** In headless chromium the `CWP-029` preview paints as a **solid black
rectangle** rather than the bill. Three checks now say the product is not at
fault, and the third is conclusive:

1. the served file is a valid PDF (`%PDF-1.4`, ~7.4 KB, two fetches hashing
   identically);
2. the `bg-[white]` utility the frame relies on **is** emitted into the built
   stylesheet, so it is not a class compiling to nothing (`DEF-974`'s shape);
3. **the PDF's own text was extracted and read.** It is a complete bill — 69 text
   runs, `UTILITY BILL`, the utility's name and telephone, the account number,
   the customer, the service address, the bill number, both dates, the period and
   the per-service lines. **A blank or black document could not contain them.**

So the black rectangle is the headless shell having no PDF viewer, and nothing
else. **Not filed, and no longer merely unfiled** — the earlier note here said
*"what would settle it is opening it in a headed browser once"*, and reading the
document's own bytes settled it for less. Recorded so the next pass does not
spend a browser on it.

⚠ **AND READING THAT PDF FOUND SOMETHING ELSE, WHICH IS DELIBERATELY NOT FILED.**
The posted bill prints **`Bill date 2026-08-02`** and **`Service period
2026-07-01  2026-07-31`** — raw ISO dates on the paper a customer holds, the same
class as `DEF-CWP-4150` one layer down. It is **not** filed here for three
reasons worth stating rather than assuming: it is `apps/billing`'s document
template and not this wave's screens; the printed bill is a **legal artefact
frozen at issue** (`BR-NOT-027`, `BR-CWP-045`), so changing how it renders is not
the same act as changing a screen and must not silently rewrite documents already
posted; and a grep of the decision log and the open-question register found **no
ruling either way**, which after `DEF-CWP-4153` this lane treats as *unproven*
rather than as *absent*. Somebody who owns billing's document template should
look, with `OQ-620`'s lesson in hand: the absence of a ruling is not permission.

---

## `CWP-027` · Your bills (wireframe P13)

**The closest match in this wave.** Kicker, title, search box, `All | Unpaid |
This year` chips, all eight columns, sortable headers, row icons and the
pagination footer are all present and in the drawn order.

| # | Type | Change |
|---|---|---|
| 27.1 | `CONTROL` | **`↓ Download all` is missing.** The drawing puts two buttons in the head — `↓ Download all` and `Pay $142.18` — and only `Pay` is drawn. `CWP-031`'s equivalent (`Download a year ↓`) ships HELD with *Downloads are not ready yet*, so the honest shape here is the same held control rather than a live one |
| 27.2 | `CONTROL` | **`Pay` carries no amount**, where the drawing writes `Pay $142.18`. ⚠ **STATED, NOT A GUESS, and the reason is a money rule.** `GET /portal/bills` serves each bill's own `owing` and NO total, so an amount here would be either a sum computed in the browser — money arithmetic in the display layer, which hard rule 2 keeps out — or one bill's figure labelled as if it were all of them. **Owed: a served `total_owing` on the bills envelope**, computed once by the server from the ledger |
| 27.3 | `FORMAT` | **No digit grouping in USAGE** (`X2`). Live draws `900 kWh`; a four-figure quantity draws `2000 kWh` where the drawing writes `4,820 gal`. The AMOUNT and OWING columns group correctly — it is the quantity that does not |
| 27.4 | `DATA` | **`0 cart · 900 kWh · 9 kgal`** — a ZERO quantity is printed for a service that was billed on capacity rather than measured. The drawing puts one meaningful figure in this column. `Bills.tsx`'s own comment says a bill with nothing measured draws an em-dash rather than a `0`; that is true of an EMPTY series and not of a series carrying a zero |
| 27.5 | `FORMAT` | Period reads `07/01/2026 – 07/31/2026` against the drawing's `1–31 Aug`. ⚠ **NOT A DEFECT AND DELIBERATELY NOT "FIXED"** — `DEF-CWP-3994` made portal dates the TENANT's own format, and inventing a compact `1–31 Aug` here would be a second date formatter beside the published one. Recorded as a divergence with its reason |
| 27.6 | `STRUCTURE` | ✅ **DIVERGENCE RECORDED AND KEPT.** The three buttons under the table — *Documents and letters*, *Where things stand*, *See what help there is* — are not in the drawing. They are `DEF-CWP-3954`'s fix: those three screens had no door anywhere in the product. Keep them |
| 27.7 | `CONTROL` | ✅ **DELIBERATE ABSENCE, ALREADY STATED IN THE CODE.** r10 rule 12's `+ Filter ▾` and `▦ Columns` are not built: a customer with eight columns has nothing to hide, and the staff column-preference route is closed to a portal session, so a portal column chooser would need a second preference store. `listTable.tsx` records this as an absence rather than drawing a dead control |

---

## `CWP-028` · One bill, line by line (wireframe P14)

**The arithmetic is right and visible**: `$197.26` charges + `$3.95` tax =
`$201.21` total, read back out of three rendered cells. The service grouping,
the `QUANTITY / RATE / AMOUNT` columns, the per-service subtotal line, and all
three rail panels (`YOUR ACCOUNT`, `READINGS THIS BILL`, `SOMETHING WRONG?`) match
the drawing.

| # | Type | Change |
|---|---|---|
| 28.1 | `CONTROL` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4149`).** The back link drew **`← ← Bills`** — two arrows. `PageHeader` renders `← {label}` and the catalogue value already began with one, in all eleven languages. The arrow is stripped from the three affected values; the wording is 29.2 below |
| 28.2 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4150`).** The subtitle read `BL-2608-000096 · 2026-07-01 to 2026-07-31 · due 2026-08-22` — three raw ISO dates — **while the readings panel further down the same file drew `07/31/2026`**. All three now go through `usePortalDate`. A regression test asserts the subtitle matches no `\d{4}-\d{2}-\d{2}`, proved red first |
| 28.3 | `CONTROL` | **The head carries none of the drawing's three actions** — `↓ PDF`, `Query this bill`, `Pay $142.18`. Only *Why is this different? →* is there. ⚠ **PARTLY BY DESIGN AND THE FILE SAYS SO:** the printed bill has its own screen reached from the body, and *Query this bill* IS in the rail exactly where the drawing also puts it. What is genuinely absent is `↓ PDF` in the head and a `Pay` with a per-bill amount |
| 28.4 | ~~`FORMAT`~~ **NOT A GAP — CORRECTED 2026-09-06** | ⚠ **THIS ROW WAS WRONG AND IS CORRECTED IN PLACE, NOT DELETED, because acting on it would have BROKEN THE BILL.** It read: *rates draw FOUR decimals against hard rule 2's display 2, filed as `DEF-CWP-4153`*. **A rate showing four decimals is RULED CORRECT.** `OQ-620`, closed 2026-08-27, PO verbatim: *"What does a tariff rate show? Four ($0.1420). A rate is not money and not a quantity - 4 decimal places"* — worked there as `8.290000` per kgal → **`$8.2900`**, zeros KEPT. Hard rule 2 was explicitly **not** changed by that ruling: money still displays 2 and a quantity at most 2 trimmed, and a RATE is a third kind — it is multiplied by a quantity before it becomes money, so its precision compounds. All three kinds live in `06-backend/core/money_fields.py`. ⚠ **THE LANE'S INSTINCT WAS RIGHT AND ONLY ITS CONCLUSION WAS WRONG:** it refused to round because `$0.0025 / kWh` would print `$0.00` beside a real charge, which is precisely the hazard `OQ-620` exists to prevent and precisely what a later lane following this row would have caused. `DEF-CWP-4153` is marked **invalid**. **The wireframe's `$8.90 / 1,000 gal` is the STALE side here** — `OQ-620` cites r10's residential bill, a customer's bill, drawing `$0.1420` — and a PO ruling beats a drawing. ⚠ **ONE THING IS GENUINELY STILL OUT, from `OQ-620` itself and not from this row: does a RATE in a CSV EXPORT write `0.1420` or `0.14`?** That is open, has a test asserting the absence of a `RATE` kind so it cannot be closed by accident, and is nothing to do with this screen |
| 28.5 | `COPY` | Line names are the engine's own labels — `electric usage tier 1 (0-500 kWh)`, `sewer usage — 40.00% of water usage charges` — where the drawing writes `Usage · first 2,000 gal` and `Sewer · share of water used`. Lower case, parenthesised ranges, and an internal tier vocabulary on a customer's bill (B14 rule 32) |
| 28.6 | `FORMAT` | The readings panel draws `2682 kgal` and `4365 kWh` — **no digit grouping** (`X2`), against the drawing's `148,220` |
| 28.7 | `STRUCTURE` | A `$0.00` line is drawn (`sewer base charge`). The drawing carries no zero rows; `BR-BIL-035`'s posture elsewhere in this file is that an unstamped figure is ABSENT rather than drawn as `$0.00` |

---

## `CWP-029` · The bill as it was printed (wireframe P15)

| # | Type | Change |
|---|---|---|
| 29.1 | `STRUCTURE` | ✅ **BUILT — the audit's "no preview" row is out of date.** The issued file is framed on screen (`DocumentPreview`, `DEF-CWP-3983`). The header records the black rectangle in headless chromium as **SETTLED, not merely unfiled** — the PDF's own text was extracted and read, and it is a complete bill, so the frame is right and the headless shell simply has no PDF viewer |
| 29.2 | `COPY` | The back link reads `Back to BL-2608-000096` where the drawing writes `← BL-2608-0141` — the destination's own name. r10 rule 1: the header's `←` NAMES where it exits to, and `← Back` is reserved for a stepper's previous step. **Not changed here**: rewriting *Back to …* across eleven languages mechanically would produce grammar nobody wrote (B14 rule 35). The doubled ARROW half is fixed — 28.1 |
| 29.3 | `CONTROL` | **The head carries no actions.** The drawing puts `↓ Download` and `🖨 Print` top right as buttons; live has the download as a bare text link at the FOOT of the card and no print at all |
| 29.4 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4150`).** The one sentence read *"…posted on 2026-08-02."* — a raw ISO date in the middle of a sentence, on the screen whose whole job is to say when the paper went out |

---

## `CWP-031` · Documents and letters (wireframe P17)

Search, the four filter chips (`All | Bills | Receipts | Letters`), sortable
headers, a row icon and the pagination footer are all present.

| # | Type | Change |
|---|---|---|
| 31.1 | `COPY` | Title reads ***Documents and letters*** where the drawing writes ***Everything we have sent you***. The kicker (`DOCUMENTS`) matches |
| 31.2 | `COPY` | The DOCUMENT cell reads `Bill for 07/01/2026 – 07/31/2026` where the drawing writes `Bill for August`. A date RANGE where the drawing names the month — and it is the column a person scans to find one letter among 41 |
| 31.3 | `STRUCTURE` | ✅ **DIVERGENCE, and it looks like an improvement.** Live adds a fifth column, `WHAT WE KNOW` (*Waiting to go*), which the drawing does not have. It answers *"did it actually go?"*, which is the second half of the same question this screen exists for. Recorded rather than removed |
| 31.4 | `CONTROL` | `Download a year ↓` is in the drawn position and ships **HELD** — *Downloads are not ready yet*, five words (B14 rule 33). ⚠ **CHECKED AGAINST `DEF-CWP-3925`: the refusal is still TRUE** — no archive endpoint exists — so the hold is correct rather than rotted |

---

## `CWP-041` · What you have paid (wireframe P27)

The columns are exactly the drawing's, the kicker renders uppercase, and 41.1,
41.2, 41.3 and 41.9 above are all confirmed built.

| # | Type | Change |
|---|---|---|
| 41.11 | `CONTROL` | **The receipt action is a loose held BUTTON under the table, not a row icon.** The drawing puts a printer icon at the end of every row that has a receipt (and correctly gives the bounced row only the eye). Live draws one `Receipt` button below the card with *Receipts arrive later this year* beneath it. **r10 rule 15 is explicit — row actions are icons with tooltips, never text links, max 2 plus an overflow** — and one control below a table cannot say WHICH row it belongs to. The hold itself is correct; its placement is not |
| 41.12 | `DATA` | **The list is scoped to the switcher's ONE account, and the route's own comment says it is not.** `portalRoutes.tsx` records for `/payments`: *"NO account id: the money list is one person reconciling one bank statement across every account they hold — the same scope `/bills` and `/documents` take"*. On a landlord holding three accounts the screen drew **1 row of 6**; the API answers all six when asked without an account. Either the scope or the comment is wrong, and a lane reading that comment would conclude the screen is broken. ⚠ **The per-account behaviour is consistent with `/bills`**, so the COMMENT is the likelier fault — recorded rather than changed, because which one is correct is a product decision |

---

## `CWP-038` · Pay now — one row added

| # | Type | Change |
|---|---|---|
| 38.10 | `CONTROL` | **The `Pay $201.21 ✓` button is disabled and says NOTHING** (`DEF-CWP-4152`). `CR-068` R3 and `BR-CWP-056` both require a control that may not be used to be visible AND say why, and this wave's demo script step 6 says every Pay control renders *"disabled, carrying its reason"*. Every other held control in the wave does — `CWP-031` *Downloads are not ready yet*, `CWP-040` *We cannot draft payments yet*, `CWP-041` *Downloads arrive later this year*. **This is the exception and it is the one that takes money.** Not fixed: the served refusal exists per account, but which of two refusals applies (no gateway, versus no method chosen) is a distinction the screen does not currently make |
| 38.11 | `STRUCTURE` | **No page head at all** — no kicker, no title. r10 rule 2: *every screen, including task pages and workflows*, uses `.page-head`. The stepper is correct (r10 rule 3) and the `WHAT THIS WILL DO` consequence box is present and correct (r10 rule 11); it is the heading that is missing |

---

## `CWP-039` · Your payment methods — one row added

| # | Type | Change |
|---|---|---|
| 39.7 | `COPY` | **A refusal that does not read as English: *"1 bounced payments block autopay."*** — a plural noun after `1`, produced by interpolating a count into a fixed string. It is five words, so B14 rule 33 is satisfied and the sentence is still wrong. Seen only because this lane's fixture planted a real bounce; on a clean account the branch never renders |

---

## `CWP-040` · Autopay — the live side, now inspected

The section above says *"live side not inspected"*. It has been.

| # | Type | Change |
|---|---|---|
| 40.1 | `COPY` | Title reads *Automatic payment*; the drawing writes ***Pay automatically each month*** |
| 40.2 | `DATA` | **The `NEXT FEW` table draws one row and its DATE is an em-dash** — `— · — · Not billed yet`. The drawing shows two rows with real dates: `14 Sep 2026 · $142.18 · SCHEDULED` and `14 Oct 2026 · — · NOT BILLED YET`, and wave G's demo script calls for *"the **real** `AutopayCaptureIntent` rows"*. A dash in the DATE column is the one cell that cannot be unknown — a scheduled capture has a date even when its amount does not exist yet |
| 40.3 | `CONTROL` | `Turn on automatic payment` ships HELD with *We cannot draft payments yet* — five words, correct, and **still true** (no gateway). Matches the drawing's greyed control |

---

## What THIS pass could not see

* **One tenant, one landlord, one width (1440), one language.** Nothing here says
  anything about a phone, a right-to-left catalogue, or a tenant offering
  different services.
* **The corrected pair was never on screen.** `BR-CWP-042`'s two rows could not be
  inspected, because the fixture will not drive `single_correction.py` (human-owned
  money math) and the sample estate plants no correction. **That is an
  uninspected rule, not a passing one.**
* **Colour was judged from a screenshot.** Where a row says *danger tier* or
  *uppercase*, the token is the authority.

---

# CR-068 wave L — four screens, added 2026-09-06

**Added by the wave L walkthrough lane**, from the same kind of side-by-side the
header describes: `wireframes/CWP-057.png`, `CWP-056.png`, `CWP-064.png` and
`CWP-045.png` against screenshots of the running product on `pine-hill`, with
the wave's own state seeded (`$412.60` overdue by 19 days, a case at the ten-day
rung, three protections with three lifetimes, a refund and two credits).
Screenshots: `/tmp/cr068-l/`.

⚠ **THE SCREENS WERE OPENED IN THE STATE THEY ARE NORMALLY IN, AND THAT TOOK A
FIXTURE.** On a freshly seeded database every Pine Hill account owes `$0.00`,
so all four of these screens draw their ABSENCE state and there is nothing to
compare with the drawing at all. The absence state was walked too, separately
(step 7 of `cr068-l-overdue-and-protections.mjs`), and it is correct on all
three screens that have one.

⚠ **THREE OF THESE ROWS ARE ALSO DEFECT ROWS**, because they are behaviour
rather than layout: `DEF-CWP-4142` (fixed), `DEF-CWP-4143`, `DEF-CWP-4145`,
`DEF-CWP-4146`. Where a row has a defect id, the register carries the escape
reason and this file carries the picture.

⚠ **`X1` IS LIVE ON ALL FOUR OF THESE SCREENS AND IS NOT REPEATED PER ROW.**
Every date on every one of them is a raw `2026-11-30`, where all four drawings
write `30 November 2026`. It is the cross-cutting formatter and it is the single
most visible difference between these drawings and this product.

---

## `CWP-057` · What happens if this is not paid (wireframe P43)

The most consequential screen in the portal. Structure is RIGHT — two columns,
timeline card left, cost panel right, warning panels below it — and the money is
right. What differs is one missing rung, one missing control, and two duplicated
strings.

| # | Type | Change |
|---|---|---|
| 57.1 | `DATA` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4142`).** The ladder had FOUR rungs and the drawing has six; the missing one was *Final notice*, and it could never be drawn: `disconnects.case_payload` did not serialise `next_step_due`, so `selectors._timeline`'s `notice_next` branch was unreachable and `portal.overdue.step.notice_next` was a dead string in eleven catalogues. Live went *Ten-day notice 2026-09-05* → *Supply disconnected no earlier than 2026-09-29*, telling a household when the supply goes and not when the last warning comes. Now five rungs, with *Final notice no earlier than 2026-09-19* between them |
| 57.2 | `DATA` | The sixth rung, *Late fee added · 24 Aug · `$8.25`*, is still absent and CANNOT be drawn: a late fee is an invoice line and no module publishes an account-scoped list of them. The server says so in its own payload — `problems[]` carries `late_fee_history_not_readable` — and the screen draws nothing rather than a blank date. **A stated absence with no screen presence:** the customer is not told a late fee was added at all, and the drawing shows the figure |
| 57.3 | `CONTROL` | **`DEF-CWP-4143`.** The drawing's head carries TWO controls — `Ask for a plan` and `Pay $412.60`. Live has only *Ask for a payment plan*. There is no pay control of any kind, held or otherwise, while `/pay-now` (`CWP-038`) is live. The one screen a customer opens because they have been told their supply may be cut has no door to the screen that stops it |
| 57.4 | `COPY` | **`DEF-CWP-4144`.** The page title reads *Where things stand* and the first card's section title, one line below it, reads *Where things stand* — the identical string twice in the first 60px of content. The drawing's title is the FIGURE, *$412.60 is overdue by 19 days*, with the card titled `WHERE THINGS STAND`. `Overdue.tsx` already flags the title choice in its own comment as wanting a decision; this is the cost of the current one |
| 57.5 | `CONTROL` | **`DEF-CWP-4144`.** The rail's second navigation button is labelled *Something is holding this* — the heading of the panel immediately above it, not a verb. r10's grammar for a navigating control is `Verb →`. So that string also appears twice, and the button does not say what pressing it does. Its neighbour, *See what help there is*, is a verb phrase but carries no `→` |
| 57.6 | `DATA` | ⚠ **NOT A DEFECT — a divergence with a reason, recorded so nobody "fixes" it.** The drawing's cost panel reads `New deposit $150.00` and `If it goes that far $657.60`. Live reads `New deposit — required, ask us the amount` and `So far that comes to $507.60`, with the note *A new deposit would be on top of this.* **No read in this product prices a reconnection deposit** (`OQ-CWP-1600`, open): the case records WHETHER one is required and nothing says what it costs. `$507.60` is `$412.60 + $95.00`, added up in the browser from the parts on screen and compared against the printed row. **The `$657.60` in the wave L demo script is therefore unreachable until that question is answered, and the demo script should not be read as a figure the product owes.** |
| 57.7 | `FORMAT` | The reconnection fee is the tenant's own `CC-RECON` row, read through `disconnects.reconnection_terms` — the screen quotes no price of its own. Confirmed live at `$95.00` after seeding that charge. Worth recording because it is the one number here a utility can change |
| 57.8 | `STRUCTURE` | The drawing's timeline rows carry a right-hand detail column (*by email and post*, *delivered by hand or by tracked post*, *reconnection is charged*). Live has label + date and nothing else. Two of those three are honest absences — nothing in this product records how a notice was served (`DELIVERY_UNAVAILABLE`) — but *reconnection is charged* is a fact the cost panel already holds |

---

## `CWP-056` · Help paying (wireframe P42)

Three cards, the moratorium as a fact with no button, and the ask that creates
no protection — **all three of the rules this screen exists for are correct in
the browser.** The differences are copy and emphasis.

| # | Type | Change |
|---|---|---|
| 56.1 | `COPY` | The drawing has a description under the title — *There are three things we can do. Ask before the final notice and all three stay open.* Live has **no description at all**. The second sentence is deliberately not shipped (`OQ-CWP-1601`: nothing in this product closes any of the three routes, so saying they "stay open" until the final notice would close a door the product would still open) — **but the first sentence is simply missing**, and it is the one that tells a frightened person there are three things to try |
| 56.2 | `COPY` | *Spread it out* reads *"Pay what you owe over up to twelve months. Someone in the office sets it up with you."* The drawing reads *"Pay `$412.60` over up to twelve months. Late fees stop while you keep to it, and so does any disconnection."* **Two losses:** the customer's own figure, and the fact that late fees and disconnection both stop — which is the reason to take the plan. The second sentence the product substitutes is `BR-CWP-066`'s ruling (a clerk grants it) and is right to be there; it replaced a fact rather than joining it |
| 56.3 | `COPY` | The drawing **bolds** *"It has an expiry date and it is not permanent."* inside the certificate card, and bolds *1 December and 1 March* inside the moratorium bar. Live bolds nothing in the card, and in the bar the bold begins mid-sentence and runs to the end: *"Nobody in this state is disconnected **between 2026-12-01 and 2027-03-01, whatever they owe. You do not have to ask for that.**"* The emphasis lands on the whole clause instead of the dates. Same class as 34.7 / 37.8 / 39.4 |
| 56.4 | `CONTROL` | The three card actions are drawn at the SAME weight in the wireframe (dark outline), with *Ask for a plan* greyed because the drawing predates `BR-CWP-066`. Live gives *Send a certificate* the filled brand primary and the other two an outline. ⚠ **AND WHEN IT IS NOT READY IT IS A DISABLED PRIMARY**, which on Pine Hill's palette renders as a large salmon block — so after the ask, the ONE control that cannot be pressed is the most visually prominent thing on the screen. Not the danger tier (checked: `CommitButton` renders `Button variant="primary" disabled`), but it reads like an alarm |
| 56.5 | `STRUCTURE` | The confirmation panel puts an empty line between *We have your request. Quote SR-26-0013 if you ring us.* and *Nothing is on hold yet…* — two `<p>`s with a gap where the drawing has none. Minor, but it is the panel that tells somebody no hold exists yet |
| 56.6 | `FORMAT` | The `InfoBar`'s leading `i` is a small brand-red letter where the drawing uses a muted rule. Cosmetic |

---

## `CWP-064` · What is protecting your supply (wireframe P50)

**The three lifetimes are RIGHT and this is the screen where that matters most:**
the certificate names `2026-11-30` and says in words it is not permanent; the
plan hold reads *no date — see below* with none invented; the moratorium runs
from the record. All three sentences are different. The debt warning is on the
screen. The layout and the card titles are where it parts from the drawing.

| # | Type | Change |
|---|---|---|
| 64.1 | `CONTROL` | **`DEF-CWP-4145`.** The drawing puts `Send a new certificate` on the certificate card and `See the plan` on the plan card, and NOTHING on the moratorium — the three-way difference is the drawing's point. Live has no action on any of the three, so the moratorium's deliberate emptiness says nothing, because its neighbours are empty too. `ProtectionCard` **has** an `action` prop and renders it; `OneProtection` passes it on no card. Hard-won law 2 exactly |
| 64.2 | `STRUCTURE` | The drawing puts `WINTER MORATORIUM` in the RIGHT RAIL beside the debt warning, with the certificate and the plan stacked in the main column — so the two things you can act on are together and the two things you cannot are together. Live stacks all three in the main column and the rail holds only the warning |
| 64.3 | `COPY` | Card titles are **lower case**: *doctor's certificate*, *payment plan*, *winter moratorium*. They come from `portal.protections.kind.*`, which are written for use INSIDE a sentence (*"A doctor's certificate is holding your supply"*) and are correct there. As panel headings they read as a mistake. The drawing has `A DOCTOR'S CERTIFICATE`, `YOUR PAYMENT PLAN`, `WINTER MORATORIUM`. **One catalogue entry doing two jobs**, and X3 is the same shape |
| 64.4 | `COPY` | No description under the title. The drawing has *Three different things, and they do not last the same way.* — which is the sentence that explains why the three cards look different, and without it the reader has to infer it |
| 64.5 | `COPY` | The chip on a plan hold whose plan is not current reads **`NOT STARTED YET`** beside *since 2026-08-24* — a date thirteen days in the past. `protections_for` computes `in_force = started and not lifted and live`, and the chip has only three words for four states, so *the plan is not current* is rendered as *it has not started*. On the screen whose whole job is to tell somebody what is holding their supply, that is a false statement. **Filed as `DEF-CWP-4154`** |
| 64.6 | `COPY` | The warning panel reads *A hold stops a disconnection. It does not stop the debt.* The drawing adds *Interest and the balance carry on underneath.* and a ⚠ glyph. The first two sentences are the rule (`BR-CWP-091`) and are present; the third is the concrete consequence |

---

## `CWP-045` · Credits and refunds (wireframe P31)

The screen's argument — *a credit comes off your next bill, a refund is money
sent back* — is on the screen, the refund's four steps are right, and the credit
figure is re-read on every load (proved by issuing one between two loads: the
count went 2 → 3).

| # | Type | Change |
|---|---|---|
| 45.1 | `STRUCTURE` | **`DEF-CWP-4146`.** One column where both the drawing AND `10-execution-plan.md` task L2 say two — L2 specifies *"`CWP-045` (T4; two halves and the separating sentence)"* and the drawing puts `A REFUND ON ITS WAY` and `CREDITS ON THE ACCOUNT` side by side. `MoneyBack.tsx` is `flex flex-col gap-4`. Stacked, the two halves read as one list, which is the confusion the screen exists to end. The kit already has `TwoCol` and the other two screens in this wave use it |
| 45.2 | `STRUCTURE` | The drawing attaches each fact to the STEP it belongs to — *Raised · 18 Sep `$89.80` after your final bill* · *Sent · 21 Sep cheque #10241, to the address you gave us*. Live puts the amount, the method sentence, the fallback reason and the posted-to address in a block ABOVE the timeline, and leaves the steps carrying bare dates. Same facts, and the drawing's arrangement is the one that answers *what happened on the 21st* |
| 45.3 | `FORMAT` | ⚠ **NOT A DEFECT — a divergence with a reason.** Credits render **negative**, `-$25.88`; the drawing prints `$25.88`. A credit note is stored at or below zero by a database CHECK added after two writers stored opposite signs (`DEF-085`), and this screen renders the sign the server sent and takes no absolute value — deliberately, and its own docstring says why. Recorded so the drawing is not used to argue the sign away |
| 45.4 | `STRUCTURE` | The separating sentence sits OUTSIDE both panels, grey, at the foot of the page. The drawing puts it INSIDE the credits panel under the table, where it is next to the thing it is disambiguating |
| 45.5 | `DATA` | `USED ON` correctly shows the bill NUMBER (`BL-L-0141`), never an id — B14 rule 31 holds here and on all four screens (asserted: no uuid, no `BR-`/`OQ-`/`DEF-` id anywhere in the DOM of any of them) |

---

## What this pass could not see

* **One tenant, one width (1440×1000), one account per state.** Nothing here says
  anything about a phone, a landlord with four accounts, or a long utility name.
* **The absence states were walked but not photographed against a drawing** — the
  wireframes draw the populated screen only.
* **Colour was judged by eye from a screenshot**, as the header warns; the
  `CommitButton` tier in 56.4 was settled by reading the component instead.

---

# CR-068 wave Q — the money screens, with the rails switched on

**Added 2026-09-06** by the wave Q walkthrough lane
(`10-scripts/render-checks/cr068-q-pay-now-autopay-refunds.mjs`, written because
the plan named it at line 805 and no such file was on disk — `DEF-CWP-4128`).
Screenshots at 1440×1000 on `pine-hill`, against the four PNGs in `wireframes/`.

⚠ **THREE OF THESE FOUR SCREENS WERE ALREADY INSPECTED THIS MORNING** — wave G
took `CWP-038` and `CWP-040`, wave L took `CWP-045` — and their rows are right.
**What this pass adds is the states their fixtures could not reach**, and that
is the whole reason it found anything at all:

| What their fixture had | What this one has | What it made visible |
|---|---|---|
| no payments provider connected | `payments_sandbox`, `behaviour: approve` | the Pay control LIVE, pressed, and money moving — so 38.10's refusal is a STATE, not a permanent fault |
| no saved instruments | `Chase ••••4021` verified · `Visa ••••8812` | the method list, its ordering and its `Verified` presentation |
| no voided refund | one issued, one voided | `45.6` and `45.7` below — both customer-facing, both now fixed |
| no approved portal fee request | `SR-26-0006`, `$335.00` | `CWP-050`, which **no pass had opened** |

**`CWP-050` had never been looked at by anybody**, and neither had a fee quote.

---

## `CWP-045` · Credits and refunds — two rows wave L's fixture could not reach

Wave L's `45.1`–`45.5` stand and are not restated. These two are what a VOIDED
refund on the screen shows, which needs a fixture holding a live refund AND a
cancelled one at once — a state no unit test and no seeded database had.

| # | Type | Change |
|---|---|---|
| 45.6 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4131`).** The void chip read **`CANCELLED ON 2026-08-28T02:08:26.806734+00:00`** — a machine instant with microseconds and a UTC offset, on a customer's screen — and the four timeline steps read `2026-09-03`. `MoneyBack.tsx` interpolated `voided_at` and `step.on` straight into the catalogue sentence. It reads `08/27/2026` now, through `usePortalDate()`, **which already existed and which `bills/Bills.tsx` already used**: this is hard-won law 2 seen from the consuming side. ⚠ The date moves by a day against the raw string, and that is `IS-8` working — an instant displays in the TENANT's zone, which is the half that once made a payment taken at 7pm local show as the next day. ⚠ **THE DRAWING'S `18 Sep` IS NOT A THIRD FORMAT TO BUILD**: seven date formats are a tenant setting (`core/numbering` · `DateCell`), `DD-MMM-YY` is one of them, and Pine Hill is set to `MM/DD/YYYY`. The drawing shows a tenant who chose differently |
| 45.7 | `COPY` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4132`).** Every refund panel carried the one fixed heading *A refund on its way*, so the CANCELLED refund was announced as money that is coming — **one line above a chip saying the opposite**. It reads *A refund we cancelled* now, in all eleven catalogues, chosen by the refund's own state. ⚠ **THE DOM TEST ASSERTED THE WRONG HEADING AND PASSED** — `MoneyBack.dom.test.tsx` TC-4 called `findByText("A refund on its way")` on a voided refund, so the case written to prove a voided refund STAYS on screen was pinning the sentence that made it wrong. Corrected in the same commit, and worth more than the fix: a fixed title over a variable state is a claim the component makes on the data's behalf, and it goes false the first time the data does something the author was not picturing |

---

## `CWP-040` · Autopay — the control's painted width, and what the red panel is

Wave G's `40.1`–`40.3` stand. `40.3` is re-confirmed: the refusal is *We cannot
draft payments yet*, five words, and still true.

| # | Type | Change |
|---|---|---|
| 40.4 | `CONTROL` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4133`).** *Take it from* rendered as a **667px full-width bordered bar** reading *Your payment methods* — not one of the kit's two button sizes (B14 rule 36, r10 rule 5). It is the identical fault `DEF-CWP-3973` fixed on `CWP-039` the same day, with the cause row `39.5` already states in general terms: **a control placed directly in a `Card`, which is `flex flex-col`, stretches to the card**. Measured in the browser: **667px before, 175px inside a 701px card after.** ⚠ **THE CLASS LIST IS IDENTICAL EITHER WAY**, so no test, no `tsc` and no gate can see it — the walkthrough now measures the painted width as a FRACTION of the card, and that assertion was proved red at 667px before it was trusted green. ⚠ **AND THE LESSON IS ABOUT THE FIRST FIX:** when a defect's cause is written down as a general rule, the fix is not finished until somebody greps for the other places it is true. `39.5` named one screen |
| 40.5 | `STRUCTURE` | ⚠ **THE RAIL'S RED PANEL IS A BUILD ANNOTATION, NOT SCREEN COPY — DO NOT BUILD IT.** The `CWP-040` entry above lists *"a red-bordered panel carrying the promise-nobody-can-keep sentence"* among the things to open the live screen against, and read as an instruction it would put **three sentences of engineering prose on a customer's screen**, which B14 rule 32 forbids outright. The same panel appears on `CWP-038.png` (*"This screen cannot be built yet. Nothing in the product can charge a card or a bank account."*) and on `CWP-050.png` (*"Fees, quotes and pay-now-or-later are all modelled."*) — **it is the drawing telling US what is missing**, which is why the `P24`/`P26`/`P36` headers all read `BLOCKED`. The customer-facing form of it is the held button's five-word reason, and that is what all three screens ship. `CWP-038` has already replaced its panel with the amber `TESTING` notice, which is a fact about the tenant rather than about the build |
| 40.6 | `DATA` | ⚠ **ROW `40.2` IS HALF RIGHT AND THE HALF THAT IS WRONG WOULD SEND A LANE AT THE WRONG FAULT** — stamped here rather than rewritten, as `DEF-CWP-3993` established for this file. `40.2` says *"a dash in the DATE column is the one cell that cannot be unknown — a scheduled capture has a date even when its amount does not exist yet"*. True of a **SCHEDULED** row and the drawing's first row is one. **The row live draws is `NOT BILLED YET`**, the drawing's SECOND row, where the drawing prints a dash too — and `Autopay.tsx` argues the case explicitly: nothing in this product answers an account's next due date before the bill is made, so a date there would be invented. The real gap is that **the SCHEDULED row is missing entirely**, and the server already names why: `intent_recording_has_no_caller` — `BR-PAY-015` records the intent at bill issue and `apps/billing/issue.py` does not call `record_intent_at_issue`. **So the work is in billing, not in this screen's date cell** |

---

## `CWP-050` · Fees to pay (wireframe P36) — **opened for the first time**

No pass had ever drawn this screen. The arithmetic is right and is the wave's
signed figure: `$185.00` + `$150.00` = **`$335.00` to pay now**, with `$25.00`
waived, struck through (a real `<s>`, `text-decoration-line: line-through`
confirmed from the browser) and in **neither** total.

| # | Type | Change |
|---|---|---|
| 50.1 | `CONTROL` | **`Pay $335.00` is in the wrong place.** The drawing puts it **top right, on the title line**; live puts it inside the card, under the totals. The page head EXISTS here (`FeesPage.tsx` composes the shared `PageHeader`), so this is delta `X4`'s missing top action row on a screen that already has somewhere to put it. **Not fixed and the reason is worth stating:** `FeesView` fetches the quote and the head is rendered by the page above it, so moving the button means lifting the query — a restructure, not a copy edit, and the control is held meanwhile |
| 50.2 | `DATA` | **The `Security deposit · On your first bill · $150.00` row and the second total are ABSENT, and that is honest rather than missing.** `paying.py` answers `on_first_bill: null` with the reason named — `deposit_not_priced`: *"this address's plan prices no deposit for a residential customer… a zero would state that a deposit was assessed and set to nothing, which is a different fact."* Live prints the grey line *Your deposit is not priced here — the office will tell you.* **So the gap is in the seeded PLAN, not in the screen**, and `US-CWP-050` TC-4 (*the deposit is in neither total*) is unproven on this estate rather than failing. A fixture that priced a residential deposit would draw both |
| 50.3 | `STRUCTURE` | The drawing's first rail panel carries **two** sentences — *Work starts once the fees are paid.* **and** *The deposit is returned when you close the account, with interest.* Live carries only the first; the deposit sentence is conditional on `on_first_bill` and so disappears with `50.2`. Worth pairing with `50.2` when the plan prices a deposit: one fix restores both |
| 50.4 | `FORMAT` | **The `BEFORE YOU PAY` panel is outlined in BLUE.** `Panel tone="info"` paints blue, and *nothing else in this product is blue — the brand is the red the drawing uses throughout*, which is delta row `41.10`'s open finding confirmed on a second screen. The drawing's equivalent box is a neutral card with a small orange `i` |
| 50.5 | `STRUCTURE` | ⚠ **DIVERGENCE RECORDED AND KEPT.** Live adds a `QUESTIONS` rail panel with a door to `/ask-a-question`, which the drawing does not have. It is a real destination to a live screen and it is the right thing to offer beside a bill somebody may query — kept, and recorded so it is not read as drift |
| 50.6 | `CONTROL` | `Ask a question` carries no arrow. r10 rule 4: `Verb →` navigates. It navigates |
| 50.7 | `CONTROL` | ✅ **CORRECT AND WORTH RECORDING.** The Pay control is held on `no_fee_payment_path`, visible and disabled with its reason — and **there is no amount box on the screen at all**, so `US-CWP-050` TC-6's refusal of a part payment is STRUCTURAL rather than a validation message. Asserted as `input` count zero |

---

## `CWP-038` · Pay now — the other half of `38.10`, with rails connected

| # | Type | Change |
|---|---|---|
| 38.12 | `CONTROL` | ⚠ **`38.10` IS A STATE, NOT A PERMANENT FAULT, AND THIS IS THE OTHER HALF OF IT.** That row records the Pay button *"disabled and saying NOTHING"* — true of a tenant with no payments provider, which is every tenant `seed_portal_demo` makes. With `payments_sandbox` connected and a method saved, the control renders **`Pay $957.07 ✓`, enabled, brand primary, in the button row at the foot of the card** exactly as the drawing puts it, and pressing it wrote one payment row, one receipt and one audit entry, and `CWP-041` read *Cleared* the same minute. **`38.10`'s point stands** — the silent disabled state is real and is the one that takes money — and it is reached only when the refusal has nothing to say, which is worth knowing before somebody hunts it on a working tenant |
| 38.13 | `STRUCTURE` | ⚠ **`38.11` RESTS ON r10 RULE 2 ALONE AND NOT ON THE DRAWING** — stamped, not rewritten. `CWP-038.png` shows the browser chrome and then the **stepper**; it draws no kicker and no title. So the product and the drawing AGREE here and the missing page head is a style-rule finding, which is a different (and weaker) claim than the row's placement in a wireframe-delta file implies. r10 rule 3 (a 2+ stage flow uses a stepper) is satisfied, and `08-screen-layouts.md` is the document that would settle whether a stepper replaces a head |
| 38.14 | `STRUCTURE` | **The method list's order and its `VERIFIED` presentation.** The drawing lists *Bank account · Chase ••••4021* **first and pre-selected**, with a green `VERIFIED` chip on the right; live lists *Visa ••••8812* first, pre-selects the card, and renders the bank's status as the inline text *· Verified* after a middot. Two separate things: `38.8` already records the missing chip and is **confirmed still open**; the ORDER is new here, and it decides which instrument a customer charges by default |
| 38.15 | `COPY` | ✅ **DIVERGENCE RECORDED AND KEPT.** The consequence box draws a **fourth** bullet the drawing does not have — *A payment cannot be changed afterwards, only reversed.* That is hard rule 4 made visible at the one moment it matters, on the screen r10 rule 11 exists for. Keep it |
| 38.16 | `COPY` | Rows `38.6` (money **bold** inside each amount option) and `38.7` (*Just the August bill*, a month rather than a bill number) are **both confirmed still open** — live reads *Everything you owe — $957.07* and *Just bill BL-2607-000004 — $459.31*, unbolded. `38.6`'s two-line hunk in `primitives.tsx` is still unclaimed |

---

## What this pass could not see

* **One tenant, one account, one width (1440×1000), one language.** Nothing here
  says anything about a phone, a landlord, or a right-to-left catalogue.
* **The deposit line and its total were never on screen** (`50.2`) — the seeded
  plan prices no residential deposit, so `US-CWP-050` TC-4 is UNPROVEN rather
  than passing. That is an uninspected rule, not a clean one.
* **The `SCHEDULED` autopay row was never on screen** (`40.6`) — nothing writes
  `AutopayCaptureIntent`, so the drawing's first `NEXT FEW` row cannot be
  compared against anything.
* **Colour was judged by eye from a screenshot** (`50.4`); the token is the
  authority, and `41.10` is where the blue belongs as an open question.

---

# ⚠ THIRD PASS — CR-068 wave M's five screens, 2026-09-06

**`CWP-042` · `CWP-043` · `CWP-044` · `CWP-063` · `CWP-066`.** Compared
side by side against `wireframes/CWP-04{2,3,4}.png`, `CWP-063.png` and
`CWP-066.png`, on tenant `pine-hill` at 1440×1000, from the first browser
walkthrough this wave has ever had (`10-scripts/render-checks/cr068-m-plans-and-level-pay.mjs`,
which did not exist until today although the execution plan named it).

⚠ **THE FIXTURE IS PART OF THE EVIDENCE.** `seed_portal_demo` alone leaves no
level-pay row, no offered plan and no portal login, so three of these five
screens draw a *nothing here* branch that photographs perfectly and shows none
of what the drawings show. `cr068-m-fixture.py` puts the demo script's own state
in front of the browser first. **A pass that had skipped it would have reported
these screens as clean.**

⚠ **FOUR ROWS BELOW ARE ALREADY FIXED**, in the same session that found them, and
say so inline. The rest are open, each carries a defect id, and **each is
registered as a known gap in the walkthrough** — so the run counts them while
they are open and goes RED the day one is closed and its row is not deleted.

**So the file now covers nineteen of the seventy-seven wireframes.** The other
fifty-eight are uninspected and their absence here still means nothing.

---

## `CWP-042` · Ask for a payment plan (wireframe P28)

The arithmetic is right and it is the thing that matters most: driven live, six
instalments summed to the total the same screen printed, to the cent, and the
remainder sat on the last row. `$172.20` less `$40.00` over six is five of
`$22.03` and a final `$22.05` — `GT-47`'s own frozen shape, confirmed from the
engine. What differs is the shape of the page and one sentence that was not true.

| # | Type | Change |
|---|---|---|
| 42.1 | `STRUCTURE` | **`DEF-CWP-4182`.** The drawing puts the form, the *WHAT THIS WILL DO* box and the two buttons in the LEFT column, and the instalment table in the RIGHT rail. Live is **inverted**: the table sits under the form on the left, and the consequence box with *Ask for this plan ✓* is in the rail. So the six figures a customer is agreeing to and the button that agrees to them are in different columns. Asserted on the browser's box model, not on DOM order |
| 42.2 | `CONTROL` | **`DEF-CWP-4182`.** *Spread it over* is a `<select>` reading **`6 months`** in the drawing and a bare `<input>` reading **`6`** live. Two losses: the unit disappears from the field (the helper line below still says *Between 2 and 12 months*), and a bounded choice becomes typeable — which is the only reason `13` reaches the server at all |
| 42.3 | `COPY` | **`DEF-CWP-4182`.** The stepper reads *What you owe · **2** Choose the instalments · **3** Agree*, and **step 3 cannot be reached**: pressing the commit goes straight to *We have your request*. `OQ-1391` closed on 2026-09-04 with option (a) — the customer only ASKS, a clerk grants — so *Agree* is a step this flow no longer has. The ruling landed and the stepper did not move. There is also no *Back*, which the drawing has beside the commit |
| 42.4 | `COPY` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4140`).** *The last instalment carries the rounding.* was printed unconditionally. Driven live at `$120.00` over six — six instalments of `$20.00`, which the wave M demo script names as its own second case — the screen still said it. `carries_the_rounding` meant *is the last row*, because `build_schedule` sets `final` whether or not a remainder exists. It now means what its name says and the caption follows the server |
| 42.5 | `COPY` | **`DEF-CWP-4141`, open.** Thirteen months is refused with *"We could not work that out. Please check the dates."* The dates are fine; the term is not. The server answers `portal.plan.termOutOfRange` with `min: 2, max: 12` and the screen catches every failure into one generic sentence, so the refusal points at the wrong field and contradicts the helper line six inches above it |
| 42.6 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4138`).** Due dates read `2026-10-14`. Pine Hill's Regional setting is `MM/DD/YYYY`, and `usePortalDate` — the hook `DEF-CWP-3994` shipped for exactly this — was not used by any wave M screen. Now `10/14/2026` |
| 42.7 | `STRUCTURE` | The drawing shows the money as `$40.00` in *Something up front?*; live shows `40.00` in the input. Cosmetic, and arguably right for an editable field, recorded so the next reader does not re-report it |
| 42.8 | `DATA` | ⚠ **NOT A DEFECT — recorded so nobody "fixes" it.** The drawing's figures are `$172.20` / `$132.20`. Live shows whatever the account owes, because the preview reads the account's real arrears — on the walkthrough's account, `$585.94` over six. **The demo script's figure is a story, not a number the screen owes**; what the screen owes is that Σ rows equals the printed total, which is what the walkthrough asserts |

---

## `CWP-043` · Your payment plan (wireframe P29)

Six rows in four states, the signed figures, the per-plan election read from the
row rather than promised — the rules this screen exists for are right in the
browser. Two things are missing from the head, and one of them matters.

| # | Type | Change |
|---|---|---|
| 43.1 | `CONTROL` | **`DEF-CWP-4181`.** The drawing's head carries **two** controls, *↓ Agreement* and ***Pay the next one***. Live has only *Agreement*, held. There is **no pay control of any kind**, held or otherwise, on a screen that says *DUE IN 9 DAYS* — while `/pay-now` (`CWP-038`) is live and routed. This is row 57.3 on a second screen, so the fault is now known on both screens whose job is to tell somebody money is due |
| 43.2 | `COPY` | The drawing's title is a STATE — *Your plan is on track* — with the lead *Three of six paid. **Next payment 14 December.*** Live titles it *Your payment plan* and leads with *3 of 6 paid.* **The next payment date is absent**, and it is the one fact a customer opens this screen for. (The date is on the table two inches below, so this is emphasis rather than data) |
| 43.3 | `COPY` | **`DEF-CWP-4183`.** *Your payment plan* is the page heading and *YOUR PAYMENT PLAN* is the first card's title, one line apart. The drawing titles that card for its contents. Four of wave M's five screens do this |
| 43.4 | `COPY` | The rail's three statements bold the **lead** of each in the drawing — ***No late fees*** on the amount in the plan, ***No disconnection*** for that debt. Live bolds nothing on the first two and the **whole** of the third. Emphasis lands on the clause instead of the subject; same class as 56.3 and 34.7 |
| 43.5 | `STRUCTURE` | ⚠ **A DIVERGENCE THAT IS CORRECT AND THE DRAWING IS SUPERSEDED.** The wireframe's lower rail is a red warning: *Missing **two** instalments ends the plan and the whole remaining balance falls due.* Live says *If you miss a payment — we get in touch about it. The plan stays open.* The PO ruled on 2026-08-11 *"nodrop we chase for payments until write off"*, and `record_missed_instalment` returns `active` on the tenth miss. `OQ-CWP-1720` carries the collision. **The screen is right and the drawing is out of date** |
| 43.6 | `STRUCTURE` | Live adds a *Paid up front / Payments / Taken automatically* list the drawing does not have. `US-CWP-052` §1 asks for exactly those, so this is the story ahead of the drawing, not a defect |
| 43.7 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4138`).** Same ISO dates, same fix |

---

## `CWP-063` · A plan the utility has offered you (wireframe P49)

**The one screen in this wave that was telling a customer something untrue**, and
it was on the box that says what accepting the plan does.

| # | Type | Change |
|---|---|---|
| 63.1 | `COPY` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4137`) — the most serious thing this pass found.** The consequence box ended *"Miss two payments and the plan ends, and the whole balance falls due."* The PO ruled the opposite on 2026-08-11 and the product does the opposite. Its sibling `CWP-042` printed the true sentence all along, so **one wave said two opposite things about one rule and the wrong one was on the commit screen.** It escaped because the guard exists on the other two plan screens and this screen's own test SUPPLIED the forbidden code in its fixture. Now the same sentence as `CWP-042`, in each of the eleven catalogues' own words |
| 63.2 | `COPY` | The drawing's title names the utility — ***Pine Hill*** has offered you a plan — and its lead names the clerk: ***Sarah at the office*** set this up on 2 September. Live: *A plan we have offered you* / *We have offered you a plan. The office set this up on…*. ~~The clerk's name is an honest absence (`OQ-CWP-1567`: it exists only on a pruned audit row and the screen says *We cannot show you who set this up*).~~ **ANSWERED 2026-09-08 — `OQ-CWP-1567` CLOSED, option (a) (`CR-085` `CPB-21`).** `payment_plans` keeps who offered it, so the lead now reads *«Sarah Kesler» set this up on 2 September* on any plan written since; a plan older than the column keeps the honest absence, which is why that sentence is still in the catalogues. **The utility's own name is not, and it is the word that makes the sentence feel like it came from somebody** |
| 63.3 | `COPY` | **`DEF-CWP-4183`.** Page heading and first card title are the same string |
| 63.4 | `CONTROL` | The three controls are in the drawing's order — Accept · Ask for different terms · Decline — and all three are correctly held on `OQ-CWP-1568`, which is OPEN. ⚠ **But the identical reason is printed three times, once under each button.** *Ring us to answer this offer · Ring us to answer this offer · Ring us to answer this offer.* One cause, one sentence — `AskForPlan.tsx`'s own comment makes this argument about two sentences for one cause; three copies of one is the same fault |
| 63.5 | `STRUCTURE` | ⚠ **CORRECT, AND THE DRAWING IS THE THING THAT CANNOT BE BUILT.** The drawing's ⓘ panel says *The offer stands until 16 September; after that the office has to set it up again.* No column holds that date (`OQ-CWP-1566`, open), so live says *We have not recorded a closing date for this offer.* A screen that computed one would state a deadline this product cannot enforce |
| 63.6 | `COPY` | The right rail is headed *THE PAYMENTS* where the drawing says *THE INSTALMENTS*, and the total row reads *Spread over these payments* against the drawing's *Total*. Wording, not meaning |
| 63.7 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4138`).** *The office set this up on `2026-09-02`* and *First payment `2026-09-14`* were ISO. Now the tenant's format |

---

## `CWP-044` · Level pay (wireframe P30)

⚠ **THE PASS SAW THE *ALREADY ENROLLED* BRANCH, WHICH THE DRAWING DOES NOT
DRAW.** The wireframe is the joining screen — twelve months, the average, the
rounding, the chart, *Join level pay ✓*. The fixture account is already on level
pay, so live shows one sentence and a door. Everything below is therefore about
a branch the drawing has no picture of, and **the joining screen itself remains
uncompared.**

| # | Type | Change |
|---|---|---|
| 44.1 | `COPY` | **`DEF-CWP-4183`.** *Pay the same amount every month* is the page heading and *PAY THE SAME AMOUNT EVERY MONTH* is the card's title directly beneath it |
| 44.2 | `COPY` | The drawing's lead — *We average your year and settle up once.* — is absent on this branch. The catalogue has it (`portal.levelPay.lead`); the enrolled branch does not render it, so the screen opens with a heading and then a bare sentence about the amount |
| 44.3 | `CONTROL` | *Where your level pay stands* is a plain bordered button. r10's grammar for a control that NAVIGATES is `Verb →`; this is a noun phrase with no arrow, and it is the only way out of this screen |
| 44.4 | `STRUCTURE` | The drawing's right column is a chart panel — *THIS MONTH, EITHER WAY*, twelve bars and a line at the level. The enrolled branch has no right column at all, so roughly two thirds of the viewport is empty below the fold |
| 44.5 | `DATA` | ⚠ **NOT A DEFECT.** The drawing's `$1,501.09 / $125.09 / $125.00` are the JOINING figures. Live shows `$125.00` from the enrolment record. The rounding rule is the tenant's (`BR-CWP-054`), confirmed as `whole_dollar` on the wire |
| 44.6 | — | **NOT INSPECTED: the eligible-but-not-enrolled branch**, which is what the drawing shows. It needs twelve months of billed history on an unenrolled account and the fixture has two. The walkthrough prints this as a named skip rather than passing over it |

---

## `CWP-066` · Where your level pay stands (wireframe P52)

The three tiles, the words *ahead*, the settle-up month and the change table are
all right, and the figures are the fixture's own — `$125.00` a month, `$47.30`
ahead, June. Two whole pieces of the drawing are missing.

| # | Type | Change |
|---|---|---|
| 66.1 | `CONTROL` | **`DEF-CWP-4180`.** The drawing's head carries **↓ CSV**. Live has no CSV control of any kind. The execution plan's own M2 row names it — *"`CWP-066` (T3 with `KpiRow`; CSV)"* — so it was specified, planned, and the wave was stamped BUILT without it |
| 66.2 | `STRUCTURE` | **`DEF-CWP-4180`.** The drawing's lower rail answers the question a customer on level pay actually has: *IF YOU LEFT TODAY — We would owe you `$47.30`. It would come off your next bill, not back as a cheque.* with a *Leave level pay* control. **None of it is live.** The figure is already on the screen in a tile, so the answer is a re-presentation of data the page holds; the control is a WRITE and belongs in `OQ-CWP-1568`'s family, i.e. it would be held, not live |
| 66.3 | `COPY` | The KPI tiles carry a second, dimmer label — *YOU PAY EACH MONTH **POSTING DATE***, *YOU ARE AHEAD BY **POSTING DATE*** — which the drawing does not have and which reads as a stray field name beside a customer's money. It is the `KPIStrip`'s money `basis`, drawn as a caption. The drawing's captions are sentences: *Since 1 Jan 2026*, *Paid more than used, so far* |
| 66.4 | `STRUCTURE` | The drawing's chart is headed *WHAT YOU PAID AGAINST WHAT YOU USED* with twelve months; live is headed *MONTH BY MONTH* with **one** bar (`Aug`) and an em-dash where the second series should be. That is the fixture's history rather than a screen fault — but it means **the two-series comparison this screen exists for was not actually seen**, and the chart legend rendered its second series as a bare `—` |
| 66.5 | `COPY` | The drawing's *WHAT HAPPENS IN JUNE* panel has four bullets including *You can leave at any time and pay the difference.* Live has two. The missing pair are the ones about leaving — the same gap as 66.2, in words |
| 66.6 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4138`).** The change table's *WHEN* column read `2026-07-01`; now `07/01/2026` |

---

## What THIS pass could not see

* **One tenant, one width (1440×1000), one login holding three accounts.**
* **`CWP-044`'s joining branch and `CWP-066`'s twelve-month chart**, both for the
  same reason: the fixture account has two months of billing history and the
  drawings show twelve. Both are named skips in the walkthrough rather than
  silent omissions.
* **Colour and tier by eye**, as this file's header warns — except the three held
  controls on `CWP-063`, which were read from the rendered `disabled` state.
* **Nothing about a phone.** `CWP-079`, the phone overdue view, is deferred by
  the PO and no wave M screen was opened at a narrow width.

---

# ⚠ WAVE J's PASS — 2026-09-06, and one of its three screens exists

**Added by the CR-068 wave J lane**, from `cr068-j-self-read-and-final-bill.mjs`
run against tenant `pine-hill` at 1440×1000, beside `wireframes/CWP-032.png`,
`CWP-035.png` and `CWP-067.png`.

⚠ **TWO OF THE THREE HAVE NO LIVE SIDE, AND THEIR ROWS ARE STILL WORTH WRITING.**
`CWP-035` *Send us your reading* and `CWP-067` *A visit is booked* are two of the
ten drawn-and-unbuilt screens (`DEF-CWP-3988`). This file's earlier pass wrote
*"`CWP-035` is unbuilt, so there is nothing to compare it to"* and stopped there.
**That is the wrong conclusion from a right observation:** what the drawing asks
for is exactly what whoever builds the screen will need, and writing it down now
is most of the story's specification. So both are recorded below as ONE-SIDED
rows — the drawing's column filled in, the live column stated as absent.

⚠ **AND `CWP-032` WAS OPENED IN BOTH OF ITS STATES, WHICH IS THE ONLY WAY TO SEE
IT.** `Settlement.settled` is `path is not None or remainder == 0` and a refund
picks its path automatically, so *we owe you* and *you owe us* are mutually
exclusive screens and half the rows below are invisible from either one alone.

---

## `CWP-032` · Your final bill (wireframe P18)

The shape is right and was right before this pass: two equal panels, SETTLING UP
on the left with its `KVList` and heavy total rule, WHAT HAPPENS NEXT inside it
with the red left rule, CLOSING READING on the right. The figures are the
engine's and they add up. What follows is what a person sees differently.

| # | Type | Change |
|---|---|---|
| 32.1 | `STRUCTURE` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4190`).** **The screen had NO HEADING AT ALL on the only branch a leaving customer reaches.** `{head}` was rendered in the could-not-read, still-reading and no-final-bill returns and left out of the success return, so *MOVING OUT / Your final bill* drew on every state where there is nothing to read and vanished the moment there was something. Now present and asserted by a case written on the branch WITH data |
| 32.2 | `STRUCTURE` | **`DEF-CWP-4000`.** The drawing's head carries **↓ PDF** and **Pay $63.40**, right-aligned beside the title. Live has no action row of any kind, so **a leaving customer cannot keep a copy of the last bill they will ever get**. The same missing composition as `CWP-031`'s *Download a year* and `CWP-066`'s *↓ CSV* — one fault, many screens |
| 32.3 | `DATA` | The total reads **`We owe you -$103.10`**; the drawing reads **`We owe you $89.80`**. Two differences and only one is a fixture artefact. **The FIGURE is the fixture's** — the seeded tenant pays 0% on deposits, this walkthrough's fixture sets 2%, and `$89.80` is the story's illustration rather than a ❄️ frozen figure (`US-CWP-037` carries `golden_tests: []`). **The MINUS is not.** The screen prints the server's signed remainder under a sentence that already says the direction, so a customer reads *we owe you minus one hundred and three dollars*. `FinalBill.tsx` states the choice deliberately — *"a negative remainder is drawn as we owe you $89.80 by choosing a SENTENCE, never by stripping a minus"* — and then prints the minus anyway. **Not filed: which of the two is right is a judgment for whoever owns `BR-CWP-048`'s presentation**, and the drawing is only evidence. What is certain is that the code's own docstring and the code disagree |
| 32.4 | `COPY` | The drawing's WHAT HAPPENS NEXT has **three** bullets and the first one **names the amount**: *A refund is raised for $89.80.* · *It goes to the address you gave us.* · *Allow ten working days.* Live has **two**: *We send the money back to the address on your account. Allow ten working days.* and *This is money sent back, not a credit — there is no next bill to put it on.* So live merges the drawing's second and third, and **drops the figure**, and adds the not-a-credit sentence which the drawing carries in its caption prose rather than as a bullet. The not-a-credit line is `BR-CWP-048` made visible and should stay; the missing half is that **the one panel telling a customer what is coming back does not say how much** |
| 32.5 | `CONTROL` | **`DEF-CWP-4192`.** The drawing puts **Query this reading** on THIS screen — the `$89.80` refund. It can never draw there: an automatic refund is `settled` on sight, `query_reading_open` is `not settled`, and the customer gets *"This account has settled, so a correction now takes longer. Please ring us."* before they have read the page once. The control exists only on the *you owe us* half. **So the leaving customer who is owed money — the one with the least leverage to chase it — is the one sent to the telephone** |
| 32.6 | `COPY` | With the route open, the drawing's CLOSING READING panel carries a paragraph the live screen has in neither state: *"If this reading looks wrong, tell us now. Once the final bill is settled the account closes and a correction becomes a much slower business."* Live draws EITHER the bare control (owed) OR the settled sentence (refund), never the warning that explains why now is the moment. It is the sentence that makes the button worth pressing |
| 32.7 | `DATA` | **The closing reading does not say WHICH METER it came off.** The drawing's first row is *Water · front meter → 154,310*; live is *Reading → 154310*. The server already sends `meter_service: "water"`, `meter_serial: "88-40219"` and `meter_no`, and the screen draws none of the three. On a single-water-service account nobody notices; on any account with two meters the closing figure names nothing. ⚠ Shown by SERVICE and POSITION, or by serial — never by id (`US-CWP-042` §5's own rule, and B14 rule 31) |
| 32.8 | `FORMAT` | **Quantities carry no thousands separator and money on the same screen does.** Live: `154310` and `1270 gal`, beside `-$150.00`. Drawing: `154,310` and `1,270 gal`. `formatMoney` groups digits and the reading cells are served pre-rendered as `reading_display` / `used_since_display` with no grouping, so one screen shows two conventions. Six digits is where it starts to cost a reader something |
| 32.9 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4193`).** Four raw machine dates — the period sentence, *Service to*, *Deposit held since* and *Taken on* — now go through `usePortalDate` and render `09/17/2026`. ⚠ The drawing shows *17 Sep* and *1–17 September*; `09/17/2026` is the TENANT's chosen format, which is the right answer to a different question, and the drawing's day-month wording is not reachable from the format list. Not a defect |
| 32.10 | `STRUCTURE` | **`DEF-CWP-4191`, and it is only visible on the OTHER half.** On the *you owe us* screen the panel lists `$289.10` − `$150.00` − `$16.50` and states **`$296.82`**. Those lines come to `$122.60`; the `$174.22` difference is what the account already owed, and **no line names it**. The drawing has no arrears case, so this is not a divergence from the picture — it is the picture being incomplete and the screen following it |
| 32.11 | — | **NOT A DEFECT: the address.** The drawing's bar reads `…/portal/bills/final`; live is `/final-bill`. `screenIds.ts` records the choice and its reason — a customer's final bill is not a bill in the numbered list |
| 32.12 | — | **NOT A DEFECT: the `CWP-032` badge bottom-right.** The PO's own diagnostic (CR-016 addendum, 2026-08-19, *"display that as a tag - right bottom for every UI screen so that we know which scren has a problem"*), behind `VITE_SCREEN_ID_TAG` and `pointer-events: none`. It is not clerk-facing copy and B14 rule 31/32 do not reach it |

---

## `CWP-035` · Send us your reading (wireframe P21) — **ONE-SIDED: the screen does not exist**

`/usage/submit` — the address the drawing's own bar carries — opens nothing.
There is no live column. **The rows below are the drawing read as a
specification**, because that is what they are worth now: `OQ-1393` was ruled on
2026-09-04, so this story is **unbuilt and no longer blocked**, and the next
lane's first question will be what the picture asks for.

| # | Type | What the drawing asks for |
|---|---|---|
| 35.1 | `STRUCTURE` | Kicker **READINGS**, title *Send us your reading*, and a lead that states the deadline: *The window for your route is open until 6 September.* The window is a fact about the customer's ROUTE, not about the account |
| 35.2 | `STRUCTURE` | Two columns: the form left, a narrow rail right holding LAST READING and WHAT HAPPENS TO IT |
| 35.3 | `CONTROL` | *Which meter* is a select showing **`Water · front · serial 88-40219`** — service, position and serial, never an id (B14 rule 31). One meter still draws the control, so the customer can see which one they are reading |
| 35.4 | `CONTROL` | *Date you read it* — required, a date field defaulting to today, refused outside the window with the window named |
| 35.5 | `CONTROL` | *The number on the dial* — required, and drawn as a **`DialInput`**: wide, letter-spaced digits, `1 5 8 9 4 0`, a box that looks like a meter. ⚠ **The piece EXISTS** — `DEF-CWP-3986` records it built for `CWP-017`'s six-digit code, with `tracking-dial` added to `tailwind.css` and `border-accent` rather than `--brand`, which is set nowhere in this product. Compose it; do not draw a second one (B14 rule 36) |
| 35.6 | `COPY` | The flagged state is **brand-red on the box AND a sentence under it**, and the sentence does the arithmetic for the customer: *That is 5,900 gallons in two days — about nineteen times your usual. Check the dials and try again, or send it anyway and we will look.* ⚠ **Nineteen, not eight** — the blueprint corrected its own figure in §26 |
| 35.7 | `CONTROL` | **The flagged reading can still be sent** (`BR-CWP-070`). The drawing's *Send it ✓* stays live under the red warning. A refusal here would push the customer to guess a number that passes |
| 35.8 | `CONTROL` | *A photo of the meter* — **held**, with the sentence *Optional, but it settles most questions*. ⚠ Consumer upload is a signed deferral (PO 2026-08-08, DF-4): the picker renders its sentence and **no file input**, and a posted file is refused |
| 35.9 | `STRUCTURE` | LAST READING rail: *Taken 31 Aug → 153,040* and *Expected now → about 153,300*. The second is the product doing the customer's arithmetic before they type — it is what makes a mistyped dial obvious |
| 35.10 | `STRUCTURE` | **WHAT HAPPENS TO IT — three rows, and this is r10 rule 11's *"what this will do"* box**, mandatory on any form that writes service state: *You send it · held, not billed yet* · *We check it · same rules as our own readers* · *It goes on your next bill · or we ring you if it looks odd*. It is the panel that makes *awaiting review* honest rather than a surprise |
| 35.11 | `CONTROL` | *Send it ✓* and *Cancel*, in that order, bottom-left of the form card |
| 35.12 | — | ⚠ **AND ONE THING THE DRAWING CANNOT SHOW, recorded here because it is the ruling's real cost (`DEF-CWP-4194`).** `OQ-1393` requires a **provenance flag on every customer reading** — PO, *"you will also ahve to flag that this reading is reacievd from Cosnumer"*. `READ_SOURCES` is `("ami", "manual", "import")` and B2 names the same three; the customer's own reading is **not `manual`**, which means a person the utility SENT. The catalogues already carry `portal.readings.how.self_read` — *You sent it in* — in all eleven languages, and **no row in this product can ever wear it** |

---

## `CWP-067` · A visit is booked (wireframe P53) — **ONE-SIDED: the screen does not exist**

`/requests/visits` opens `CWP-051` (the router's `/requests/:id` catch, with
`visits` read as a request id) and the API answers 404. **This one is different
from `CWP-035` in the way that matters: it is unbuilt AND blocked.** `OQ-249` —
is field work a module of its own — is OPEN on its Work half and the PO put the
whole of it at release **R5**: *"you dont need to do anything right now"*. The
drawing says so itself, in a red note on its own right rail: *"Nothing in the
product publishes a booked visit to a customer today. The job record exists; the
field-work module's scope does not."*

| # | Type | What the drawing asks for |
|---|---|---|
| 67.1 | `STRUCTURE` | Kicker **REQUESTS**, title *A visit is booked*, lead *Tuesday 15 September, in the morning.* — the date in the lead, in words, because it is the one fact the customer opened the page for |
| 67.2 | `STRUCTURE` | WHAT IS HAPPENING: *Job → Meter exchange* · *Where → 1408 Elm St · A, front boundary box* · *Which meter → Water · serial 88-40219* · *When → Tue 15 Sep, 8:00am – 12:00pm*. ⚠ The address is derived by walking to the premises (hard rule 8) and the meter is named by service and serial (rule 31) |
| 67.3 | `COPY` | **The line the drawing's own caption says earns its place:** *Nobody needs to be in. The meter is in the boundary box and the crew can reach it. Your water will be off for about twenty minutes.* — *"most of these visits do not need the customer, and not saying so costs somebody a day off work"* |
| 67.4 | `STRUCTURE` | PROGRESS — four steps with the current one marked: *Booked · 2 Sep · part of the meter exchange programme* · *Tuesday 15 September, morning · a crew is assigned* · *We read the old meter and fit the new one · the reading carries over — you are not charged twice* · *Done · the new serial appears on your equipment list*. The third step is a billing promise on a field-work screen and is the reason a customer reads it |
| 67.5 | `CONTROL` | NOT CONVENIENT? rail: *Tell us and we will book another day. There is no charge for moving it.* with **Ask for another day** and **Ask a question** |
| 67.6 | — | ⚠ **AND THE ABSENCE IS THE SPEC.** `BR-CWP-093` — no visit means the screen and its link are **absent**, never an empty panel saying a visit might happen |

---

## What THIS pass could not see

* **One tenant, one width (1440×1000), two logins**, both on `pine-hill`.
* **`CWP-032` with no deposit at all** (`US-CWP-037` TC-6 — the deposit lines
  absent rather than `$0.00`). Both fixture accounts hold one.
* **`CWP-032`'s `settlement_unavailable` branch**, which draws when the engine
  refuses rather than paying principal alone. Reaching it means a deposit with
  no receipt date, and both fixture accounts have one.
* **Colour and tier by eye**, as this file's header warns.
* **Nothing about a phone.** `CWP-078`, the phone reading screen, is deferred by
  the PO and `CWP-035` has no desktop half to narrow.

---

# ⚠ FOURTH PASS — CR-068 wave I's five built screens, 2026-09-06

**`CWP-046` · `CWP-052` · `CWP-051` · `CWP-055` · `CWP-054`.** Compared side by
side against `wireframes/CWP-046.png`, `CWP-052.png`, `CWP-051.png`,
`CWP-055.png` and `CWP-054.png`, on tenant `pine-hill` at 1440×1000, from the
first browser walkthrough this wave has ever had
(`10-scripts/render-checks/cr068-i-requests-and-disputes.mjs`, which the
execution plan named at task `I4` and which did not exist until today).

⚠ **THE FIXTURE IS AGAIN PART OF THE EVIDENCE, AND MORE SO HERE THAN IN WAVE
M.** `seed_portal_demo` alone leaves **four of these five screens in an empty
branch** — no portal request has ever been raised, so `CWP-046`'s table never
draws and `CWP-051` cannot be reached at all; `1408 Elm St · A` holds **zero
invoices**, so `CWP-055` 404s and `CWP-054`'s *Which bill* control is empty.
**And the fifth looks fine while proving nothing**: `CWP-052` renders its form
and says, honestly, that it cannot work its comparison out — which is the whole
screen. Measured over every account on the demo tenant: **0 of 73 can produce a
verdict** (`DEF-CWP-4199`). `cr068-i-fixture.py` puts the demo script's own
state in front of the browser first. **A pass that had skipped it would have
reported all five screens clean.**

⚠ **TWO OF WAVE I's SEVEN STORIES ARE NOT BUILT AND ARE NOT ROWS HERE.**
`CWP-048` *Moving out or moving on* and `CWP-049` *Documents we need from you*
have no address in the product; both are known gaps in the walkthrough carrying
`DEF-CWP-3988`. ⚠ **The execution plan says `CWP-048` is *blocked on `OQ-1392`*
and that is stale** — `OQ-1392` closed on 2026-09-04 with the PO's *"(a) ask
only"* and `BR-CWP-082` is CONFIRMED, so nothing blocks it and it is simply
unbuilt (`DEF-CWP-4200`, and the plan is corrected in the same commit).

**One row below is already fixed**, in the same session that found it, and says
so inline. The rest are open, each carries a defect id, and the two that can be
asserted mechanically are asserted in the walkthrough so they cannot rot.

**So the file now covers twenty-four of the seventy-seven wireframes.** The
other fifty-three are uninspected and their absence here still means nothing.

---

## `CWP-046` · What do you need? (wireframe P32)

The six cards are right, they are the tenant's own list rather than a literal in
the front end, and the three that are held carry a six-word reason apiece —
*Not online yet — ring us* — over screens that genuinely do not exist. The open
requests panel is a real table with the shared list-table's sort and an eye icon
for its row action. What differs is one door and two pieces of copy.

| # | Type | Change |
|---|---|---|
| 46.1 | `CONTROL` | ✅ **CLOSED 2026-09-08 (`CR-085` `CPB-11`) — AS A SWITCH AND NOT AS A SECOND SCREEN, WHICH IS RECORDED RATHER THAN QUIETLY SUBSTITUTED.** The panel carries a **Still open / All of them** control that appears the day a request finishes and is absent until then, and the full list takes the shared pager. `08-screen-layouts.md` allocates **no `CWP-###`** for the screen `All requests →` would open and `G82` refuses a portal route whose id nobody issued, so the drawing could not be built literally without minting an id. Decision log, 2026-09-08. ~~The drawing puts **`All requests →`** at the top right of the OPEN REQUESTS panel. Live has no such control, so a customer whose panel lists what is open has no way to reach a closed or older request. The component explains the absence in a comment — *"`+ All requests →` is the door to the full list and is the page lane's"* — which is a plan nobody is holding (hard-won law 1). It is a register row now rather than a comment ~~|
| 46.2 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4204`).** The RAISED column printed the wire's `2026-09-06`. Pine Hill's Regional setting is `MM/DD/YYYY` and the drawing writes `2 Sep 2026`. It now goes through `usePortalDate` like the other seventeen portal files, and the column SORTS on the ISO string still |
| 46.3 | `COPY` | The status chip reads **WE NEED 2 DOCUMENTS**; the drawing writes **WE NEED TWO DOCUMENTS**. The catalogue's `_one`/`_other` interpolates the count as a numeral. Small, and it is the one place on this screen where a customer is spoken to in digits |
| 46.4 | `COPY` | ✅ **CLOSED 2026-09-08 (`CR-085` `CPB-05`).** The column reads **`A bill you queried — BL-2608-000044`** — a KIND CODE derived on the server from the marker its own write put there, with the catalogue writing the word (B14 rule 35). None of the clerk's sentence reaches the customer, and a test asserts that ABSENCE first. ⚠ **AND THE SAME STRING WAS BEING RENDERED IN A SECOND PLACE THIS ROW DOES NOT NAME** — `CWP-051`'s thread, under **You** — which is `DEF-CWP-4708`, found by walking the fix. ~~**`DEF-CWP-4198`, and it is the one row here that is about money.** The *WHAT* column is documented as the customer's own words. A bill query does not type anything into it: the write composes a sentence for the CLERK's worklist and stores it in the same column, and this table prints it verbatim — *"Queried through the customer portal bill BL-I-2608-0141 (2026-08-01 to 2026-08-31, **142.1800 USD**): … **Their reason:** …"*. Money at four decimals where hard rule 2 says display two, two raw ISO dates, and the customer described to themselves in the third person. **It appears only after a customer's second use of the product**, which is why five earlier passes over this screen never saw it ~~|

---

## `CWP-052` · Stop or restart service (wireframe P38)

**The arithmetic is right and it is the thing that matters most on this screen.**
Driven live three times, the comparison reproduced the wave's own demo script to
the cent and the verdict FLIPPED: five months `5 × $18.50 = $92.50` against
`$185.00 + $150.00 = $335.00` → *stopping is cheaper*; twelve months `$222.00` →
still stopping (the case `DEF-CWP-3608` corrected); nineteen months `$351.50` →
*closing is cheaper*, and the screen says so. `BR-CWP-080`'s *the account stays
open* is on the screen as a served fact, and the consequence box sits before the
commit (r10 rule 11). What differs is a control and two words.

| # | Type | Change |
|---|---|---|
| 52.1 | `CONTROL` | **`DEF-CWP-4203`.** *Why* is a **`<select>`** in the drawing, reading *The property is empty over winter*; live is an empty multiline textarea. The reason a clerk reads is unbounded free text where the drawing offers the utility's own list — the same loss `DEF-CWP-4182` recorded on `CWP-042`'s *Spread it over* |
| 52.2 | `COPY` | **`DEF-CWP-4203`.** The consequence box is headed **WHAT THIS WOULD MEAN**; every drawing and every other consequence box in the portal says **WHAT THIS WILL DO** |
| 52.3 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4204`).** *Your supply is turned off on `2026-11-01`* — the string the customer had typed into the date field, interpolated straight back. Now the tenant's own format |
| 52.4 | `CONTROL` | **THE DRAWING IS WHAT SHOULD MOVE HERE, NOT THE PRODUCT.** *Start again* is marked `*` required in the drawing. Live leaves it optional and says why in a helper — *Leave this blank if you do not know yet* — which matches the server, where a missing restart date yields no months to multiply and therefore no verdict rather than a refusal. Recorded so the next reader does not "fix" the screen to match the picture |
| 52.5 | `STRUCTURE` | The drawing's right rail is two prose sentences; live is a `KVList` with a `TotalRow` and a bolded verdict. **Live composes the kit and the drawing does not**, so B14 rule 36 favours live — noted rather than filed. Live's verdict sentence also varies with the window (*For this long, closing the account is cheaper*) where the drawing's is fixed (*For this property, stopping is cheaper*), which is the more honest sentence of the two |

---

## `CWP-051` · Track your request (wireframe P37)

**The assertion this screen exists for holds**, and it was checked over the whole
rendered page *and* the whole response body: a clerk's *"route to Tuesday crew,
low priority"* appears in neither, while the note written **for** the customer
does — so the filter is not merely an empty timeline. Withdraw is offered and is
correctly *not* the danger tier. The six-step ladder draws all six. What differs
is most of the page's furniture.

| # | Type | Change |
|---|---|---|
| 51.1 | `COPY` | ✅ **CLOSED 2026-09-08 (`CR-085` `CPB-12`).** The reference is the KICKER, the request's own derived title is the `<h1>` — read live: **`SR-26-0011` / *A bill you queried — BL-2607-000003*** — and the drawing's lead is the roll-up, **`Raised 09/08/2026`**. ⚠ The drawing's *We aim to answer within two working days* is **NOT** carried: it is a service-level promise and nothing in the product records one. ~~The drawing heads the page **`Move out · 1408 Elm St · A`** with the reference as the kicker. Live heads it *Track your request* with the reference underneath, so a customer with two open requests cannot tell from the head which one they are looking at. The drawing's lead — *Raised 2 September. We aim to answer within two working days.* — is **absent entirely** ~~|
| 51.2 | `STRUCTURE` | ◐ **PARTLY CLOSED 2026-09-08 (`CR-085` `CPB-12`).** The rail gains **Raised**, a fact the server has always sent and the rail never drew, so it renders **three** of the four. **Waiting on** already rendered whenever the server sends one — the fixture's request had none. **Last day of service stays absent and is not guessed at**: it is a move-out fact that lives inside the composed sentence and has no column (`DEF-CWP-3881`), which is `BR-CWP-093` observed. ~~The DETAILS rail is drawn with four rows and renders **two**: Reference and Open for. **Last day of service `17 Sep 2026` is missing, and so is Waiting on `Two documents`** — even though the same fact is on `CWP-046` one screen earlier, where the chip reads *WE NEED 2 DOCUMENTS* off `documents_wanted`. ⚠ The row is correctly ABSENT rather than drawn blank, which is `BR-CWP-093` observed; the walkthrough asserts that distinction, because a single `innerText()` cannot tell the two apart ~~|
| 51.3 | `STRUCTURE` | ⚠ **DELIBERATELY NOT MOVED, 2026-09-08 — stated rather than left as an open row somebody re-finds.** Moving a working textarea and a live commit into the header is pure layout with a real regression surface, and the wave that had the file open judged the head naming the request (51.1) and the ladder saying what happened (51.4) to be worth more to the customer. Still open. ~~*Add a note* and *Withdraw* are two head actions beside the title in the drawing. Live gives each a full card in the right rail, so on a short request the two things a customer can DO sit below everything they can read ~~|
| 51.4 | `DETAIL` | ◐ **PARTLY CLOSED 2026-09-08 (`CR-085` `CPB-12`).** Steps now carry a second grey line — read live: ***through this website*** under *You sent it*, ***You called it off*** on a withdrawn one, and ***We are waiting for: …*** where the server sends a `waiting_on`. `ChecklistTimeline` gained an optional `note` (B14 rule 36 — added to the kit, not to the screen). ⚠ **THE DRAWING'S THIRD DESCRIPTION CANNOT BE BUILT AND THAT IS A RULE, NOT A GAP**: *Sarah at the office* is the acting clerk, and `customers_seam._customer_visible_events` drops the actor BY NAME (`BR-CWP-052`). A test asserts its absence so nobody completes the ladder by inventing a name. ~~Every step in the drawing carries a right-hand description — *through the portal*, *Sarah at the office*, *Proof of address, and your landlord's consent*. Live's step detail is the date and nothing else, so the ladder says WHEN each step happened and never WHAT happened ~~|
| 51.5 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4204`).** Every dated step and every note printed `2026-09-06`. ⚠ It also fixes a fault the slice was hiding: `step.at` is an INSTANT, and `.slice(0, 10)` takes the UTC calendar day, which is `DEF-MET-4101`'s *one day early for any tenant west of UTC*. `usePortalDate` renders it in the tenant's own zone |

---

## `CWP-055` · Dispute a bill or a reading (wireframe P41)

Hard rule 4 holds and was proved rather than assumed: the query was sent through
the screen, and the API was then asked for the bill on either side — `142.1800`
before and `142.1800` after, with a second undisputed bill still served. A second
query on the same bill is refused with a 409 that says so by name. The two-cell
stepper is there.

| # | Type | Change |
|---|---|---|
| 55.1 | `DETAIL` | ✅ **CLOSED 2026-09-08 (`CR-085` `CPB-13`).** Read live at 1280 and at 390: the lead is **`You are querying bill BL-2608-000044, $843.36.`** and the check-and-send row is **`BL-2608-000044 · $843.36`** with **`The period it covers 07/01/2026 to 07/31/2026`** beside it. The figure comes from `getBillDetail` — the SAME read `CWP-028` makes — so the amount a customer disputes and the amount their bill shows cannot be two answers, and this screen still prices nothing. ~~**and it is the row that matters.** The drawing's first check-and-send row is **`Bill  BL-2608-0141 · $142.18`**. Live names the bill in a grey lead sentence and **shows no figure anywhere on the screen**. The one screen where a customer disputes money never states the money ~~|
| 55.2 | `STRUCTURE` | ✅ **CLOSED 2026-09-08 (`CR-085` `CPB-13`).** The box is in the main column directly above the commit, on **both** steps — `08-screen-layouts.md`'s own line for this screen is *main Card [KVList · ConsequenceBox · ButtonRow]*, and the drawing draws it only on step 2, but there are TWO commits here and rule 11 is about the button a person is about to press. ⚠ The old placement is the sharpest example of a check reading the wrong thing: *before the commit* was TRUE in DOM order, which is what the walkthrough asserted, and false on the screen. ~~The WHAT THIS WILL DO box is in the **right rail**, headed *WHAT THIS MEANS*; the drawing puts it in the left column directly above the commit. r10 rule 11's *before the commit button* is therefore true in DOM order — the walkthrough checks that — and not on the screen, where the box and the button are in different columns ~~|
| 55.3 | `STRUCTURE` | ⚠ **NOT A DEFECT, AND THIS ROW SHOULD HAVE SAID SO — corrected 2026-09-08.** The sentence it asks for is a promise the product does not keep at the moment a customer presses send: **`OQ-CWP-1681` is OPEN** and what ships is option (a), *a clerk raises `metering`'s dispute marker after reading the request*. Printing it would be hard-won law 1 on a customer's money, which is exactly what row 55.5 one line down already says about the collection hold. **Two rows of this table describe the same unbuildable class and only one was marked.** ~~The drawing's second rail panel is absent: *A disputed reading is marked on the reading itself, so the next bill knows about it too.* ~~|
| 55.4 | `CONTROL` | ✅ **CLOSED 2026-09-08 (`CR-085` `CPB-13`).** `Back` is beside `Send the query ✓` on step 2, secondary tier, and what the customer typed is still in the boxes when they land back on step 1 — a case asserts that, because a Back that empties the form is worse than none. ~~The drawing has **`Back`** beside `Send the query ✓` on step 2. Live has no way back to step 1 once the customer has moved on — the same missing control `DEF-CWP-4182` found on `CWP-042` ~~|
| 55.5 | `COPY` | ⚠ **NOT A DEFECT, AND THE DRAWING IS THE THING THAT CANNOT BE BUILT.** The drawing's box promises *We hold collection on `$142.18`. No late fee while we look.* The product cannot keep that promise — nothing records a disputed AMOUNT, `late_fee.ageable_portion` raises `NotImplementedError("OQ-420")`, and the two fallbacks are `$137.20` apart on the rule's own bill. It is `OQ-CWP-1682`, ruled on 2026-09-05, and the screen deliberately ships saying only what the code does. **Registered as a known gap in the walkthrough so it goes RED the day somebody adds the sentence back without the behaviour behind it** |

---

## `CWP-054` · Ask a question (wireframe P40)

The bill travels with the question, the topic and bill controls are both real
`<select>`s, the two telephone numbers are different numbers and the screen says
which is which, and **there is no `input[type=file]` anywhere in the document** —
the signed upload deferral, honoured, which is a claim only a browser can make.

| # | Type | Change |
|---|---|---|
| 54.1 | `DETAIL` | **`DEF-CWP-4202`.** The *Which bill* option is drawn as **`BL-2608-0141 · August · $142.18`** and renders as the number and a date. Neither the month in words nor the amount is there, so three bills in the list look alike |
| 54.2 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4204`).** That same option read `BL-I-2608-0141 · 2026-08-31`; the date is now the tenant's own format |
| 54.3 | `COPY` | **`DEF-CWP-4202`.** OR RING prints *Office (512) 555-0148* where the drawing prints *(512) 555-0148 · 8am to 5pm*. `office_hours_text` is already on the front payload this screen fetches |
| 54.4 | `COPY` | The kicker reads **REQUESTS**; the drawing's reads **HELP**, and its address is `/portal/help/ask` against live's `/ask-a-question`. Cosmetic, but the drawing files this screen under help and the product files it under requests, and only one of them can be right in a breadcrumb |
| 54.5 | `CONTROL` | ⚠ **NOT A DEFECT.** The drawing's *Attach a photo* control renders live as a held explanation — *Photos come later this year*, five words, r10 rule 33 — because customer uploads are staff-mediated by a signed deferral. The same constraint is what blocks `CWP-049` entirely. A known gap in the walkthrough, so it goes red the day a file input appears |

---

## What THIS pass could not see

* **One tenant, one width (1440×1000), one login on one account.**
* **`CWP-048` and `CWP-049` at all** — they have no address in the product. Both
  are known gaps in the walkthrough rather than rows here, because a drawing
  cannot be compared against a screen that does not exist.
* **Colour and tier by eye**, as this file's header warns. One observation that
  is deliberately NOT filed: every commit button in every wave I drawing is a red
  **outline**, and live renders solid-filled primaries. That is r10's button
  grammar against the shipped kit across the whole portal, not a wave I fault,
  and it needs whoever owns B14 rather than a walkthrough lane.
* **`CWP-051`'s refusal branch.** The fixture's request is in `more_info`, so the
  *Why we said no* card and `BR-CWP-077`'s refusal reason were never drawn.
* **The state of these screens under a failing read.** Discovered by accident and
  worth the next lane's time: when the portal's rate limiter answered `429`,
  `CWP-054`'s *Which bill* control silently offered one option and the
  suggestions panel silently vanished, with **nothing on the screen saying
  anything had gone wrong**. The walkthrough now separates *what the server
  serves* from *what the screen drew* and skips rather than passing when the
  read refuses — because the first draft of that check reported the empty panel
  as *"correctly absent, this tenant publishes none"*, which was a check passing
  wrongly about a cause it had never established.

---

# ⚠ FOURTH PASS — 2026-09-06, WAVES P AND R (`CWP-002` `CWP-003` `CWP-004` `CWP-039`)

**Written by the CR-068 waves P+R walkthrough lane**, from screenshots of the
running product on tenant `pine-hill` at 1440×1100 (P) and 1440×1200 (R), beside
`wireframes/CWP-002.png`, `CWP-003.png`, `CWP-004.png` and `CWP-039.png`.

**Three of these four screens had never been opened by anything.** Wave R's own
`R4` stamp says so in as many words — *"`CWP-003` and `CWP-004` are not opened in
a browser by anything"* — and `CWP-039` was reached by no walkthrough either.
`CWP-002` was reached by the older `cwp_portal_walkthrough.mjs` and by nothing
that compared it to its drawing.

⚠ **THE HEADER'S OWN WARNING APPLIES TO THIS PASS TOO, AND IT EARNED ITS PLACE
AGAIN HERE.** Two of the rows below say **the DRAWING is wrong and the product is
right**, and one of those two is a signed rule the drawing contradicts. A lane
that treated this file as a work list would have built both. **Open the image,
then check the rule.**

**Count after this pass: nineteen screens.** Fifty-eight of the seventy-seven
wireframes are still uninspected and their absence still means nothing.

## `CWP-002` · Quick pay, find the bill (wireframe G2)

| # | Type | What the two pictures show |
|---|---|---|
| 2.1 | — | ✅ **MATCHES.** Stepper `1 Find your bill · 2 Check and pay · 3 Done`, the two fields with the postcode described as *the service address*, the *WHERE TO FIND IT* rail and the lockout rail. The drawing's *Continue →* is greyed because it was drawn while payment rails did not exist; it is live now, which is the correct reading of `DEF-CWP-3925` (a held control over a working path) |
| 2.2 | `COPY` | The drawing's lead is *Both of these are printed on it.*; live reads *Two things off the paper, and no login needed.* **Not a defect** — B14 rule 35 puts the words in the catalogue's own language, and the live line adds the fact a stranger most needs (no login). Recorded so the next reader does not "fix" it back |
| 2.3 | `STRUCTURE` | The drawing's frame carries five nav words (Help · Visit us · Pay a bill · Report a problem · Sign in); live carries eight — Home, *Ask us for something* and *Track* were added by waves B, C and D after this drawing was made. **The drawing is out of date, not the product** |
| 2.4 | `COPY` | The lockout rail is titled *FIVE TRIES* live against the drawing's untitled warning, and the body says *After five wrong pairs this form closes for fifteen minutes*. **Verified true in the browser:** five wrong pairs were allowed and the sixth refused, and a CORRECT pair inside the window was refused too |

## `CWP-003` · Quick pay, check and pay (wireframe G3)

| # | Type | What the two pictures show |
|---|---|---|
| 3.1 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4197`).** *Due* read **`2026-08-22`** — a raw ISO date — where the drawing reads *14 September*. `usePortalDate()` was never imported although `GuestFrame` is one of the provider's two callers by design and this tenant publishes `MM/DD/YYYY`. Now the tenant's own format |
| 3.2 | `STRUCTURE` | ⛔ **THE DRAWING IS WRONG AND MUST NOT BE FOLLOWED.** `CWP-003.png` puts a **Service address** row (*1408 Elm St · A*) second in the `KVList`. `BR-CWP-019` is CONFIRMED and says a guest sees *"the amount owing and a masked name, and nothing else about the account"*. The served body carries exactly `number · amount · status · due_on · masked_name · replaced_by` and `G92` reads that selector with `ast` every run. **Building this row would put a stranger's home address on a page reachable with a bill number off a doormat.** The drawing pre-dates the rule |
| 3.3 | `CONTROL` | The drawing has an optional *Email, for the receipt* input; live has one sentence — *Email receipts are not available yet.* **Correct, and already `DEF-CWP-3951`:** the box was accepted, validated and dropped, nothing was sent to it, and writing an unverified address supplied by an anonymous caller against somebody else's account is a disclosure decision and a spam-relay surface, not a plumbing job. Hold registered as `portal.quickPay.receiptEmailHeld` |
| 3.4 | `STRUCTURE` | The drawing's second rail panel is *⚠ Nothing in the product can charge a card.*; live shows the *FIVE TRIES* panel instead. **The drawing's warning is obsolete** — the sandbox rails exist and this run paid `$303.30` through them — and carrying it forward would be a refusal over a working path |
| 3.5 | — | ✅ **MATCHES, and it is the row worth keeping:** *Billed to* renders `F. F••••••` — initial, one letter, **six dots regardless of the surname's length**. A variable-width mask leaks the length of the name it hides. Asserted by pattern, not by example |
| 3.6 | — | ✅ **B14 rule 11 MET.** *WHEN YOU PRESS PAY* stands above the commit button with three promises — the figure against the bill, *No account is created for you*, *You get a reference to keep* — and the wrapper carries the amount and the bill number as attributes so a test asserts the FACTS and not a translation |

## `CWP-004` · Quick pay, done (wireframe G4)

| # | Type | What the two pictures show |
|---|---|---|
| 4.1 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4197`) — and this is the worst thing this pass found.** *Paid* read **`2026-09-06T03:59:13.769308+00:00`**: an ISO instant, with microseconds, in **UTC**, on the receipt a person keeps. The drawing reads *2 Sep 2026, 9:47am*. **THE NUMBER THAT MAKES IT HIGH RATHER THAN COSMETIC:** the same payment now draws as `09/05/2026 23:09`, because the tenant is `America/Chicago` — so the receipt named **the wrong day**, and it is the document somebody quotes back in a dispute. `usePortalDate`'s own docstring names this exact failure |
| 4.2 | `CONTROL` | The drawing draws *↓ Receipt* and *✉ Email it to me* as working. Live draws both, **disabled, each carrying its reason** (`Receipt download is not open.` · `Sending it is not open yet.`) and each stamped `data-held-for`. **Correct under `BR-CWP-056`** — visible, disabled, reason on it, never hidden — and the attributes are the expiry test hard-won law 2 asks for. The demo script's *"↓ Receipt works without an email"* is therefore **not yet true**, and wave R's stamp is amended rather than the screen changed |
| 4.3 | `COPY` | The drawing's *We already know → Your account and your email*; live reads *The account this bill belongs to*. **Live is right:** there is no email to know, because 3.3 removed the box. A drawing that promises knowledge the product does not hold is the drawing to change |
| 4.4 | `CONTROL` | ✅ **The drawing greys *Set up a login →*; live is a real link to `/pine-hill/portal/enrol`.** Asserted BY ADDRESS, not by the words on the control — the `DEF-CWP-3925` lesson: a test that checks a screen is registered somewhere while the router mounts it elsewhere passes over two screens that both say *not built yet* |
| 4.5 | — | ✅ **`PR-21` and `BR-CWP-029` MET, and proved by trying to USE it:** after paying, a sign-in with an address derived from the reference answers **401**. A credential minted silently would look identical in every other respect |

## `CWP-039` · Your payment methods — a third row, and a confirmation

| # | Type | What the two pictures show |
|---|---|---|
| 39.7 | `FORMAT` | ✅ **FIXED 2026-09-06 (`DEF-CWP-4197`).** The **ADDED** column printed `2026-09-06` where the drawing reads *4 Mar 2026* and *2 Jun 2026*. Same cause as 3.1 and 4.1 and fixed the same way — `usePortalDate()`, never a second formatter. ⚠ **THIS IS THE THIRD SCREEN IN ONE PASS**, which is the finding: `DEF-CWP-4131` fixed wave Q's three screens the previous day and wrote *"grep every sibling screen that renders the same KIND of value"* — the guest screens and this one were not in that grep, because the grep was of wave Q |
| 39.2 | `CONTROL` | ✅ **CONFIRMED RESOLVED 2026-09-06.** The row above records that *Add a method* was *"buried inside an information notice, which is the one place a primary action should never be"*. It is now a **brand primary beside the title**, top right, exactly where the drawing puts it. Opened and photographed rather than inferred from a commit |
| 39.8 | — | ✅ **`BR-CWP-057` CHECKED, NOT ASSERTED.** No run of five or more digits appears anywhere in the DOM **or in the served body**, and no `gateway_token` leaves the edge. A `toContain("8812")` would pass just as happily over a screen printing the whole card number, which is why the check is written as an absence |
| 39.9 | — | ✅ **The autopay door is LIVE, not held.** *Set up autopay* is a real link to `CWP-040` with the standing sentence *Autopay cannot be switched on yet.* beside it. That is the right split: what cannot happen yet is the CHARGE, and saying so is `CWP-040`'s own job — shutting the door to a routed screen is `DEF-CWP-3925` |

## What THIS pass could not see

* **One tenant (`pine-hill`), one guest login and one customer login.**
* **A VOIDED bill.** `bill_lookup`'s `cancelled` branch has no reachable input in
  this build — no endpoint voids a bill — so `CWP-002` and `CWP-003` were never
  drawn in that state. `DEF-CWP-4196`, and the wave R walkthrough carries it as a
  known gap that goes RED the day one can be found.
* **`CWP-039`'s expired-card tone** (`TONE.expired → warning`). Both fixture
  instruments are current, so the third chip colour was never drawn.
* **The step-up code SCREEN.** `CWP-017` is reused for it and the refusal was
  proved at the ENDPOINT rather than by walking the code flow — which is the
  stronger half (a screen that merely disables a control is defeated by calling
  the control directly), but it is not the same as having seen the screen.
* **Colour and tier by eye**, as this file's header warns of every pass.

---

# FIFTH PASS — CR-068 wave O, 2026-09-06

**`CWP-030` and `CWP-036`, the last two portal screens with no row here.**
Written from `wireframes/CWP-030.png` and `wireframes/CWP-036.png` opened beside
the running product on tenant `pine-hill`, driven by
`10-scripts/render-checks/cr068-o-why-different.mjs` against a fixture
(`cr068-o-fixture.py`) that gives the screen four different bills to explain.

⚠ **COUNTED RATHER THAN CARRIED FORWARD, because this file's own header records
that its running total has drifted every time it was maintained by hand.** Before
this pass, **38 distinct screens** carried a section; this adds two, so it is
**40**. That number was obtained by listing the `##` screen headings and taking
the unique ids, which is what the header tells a reader to do instead of trusting
a sentence.

⚠ **EVERY ROW BELOW WAS READ OFF A RUNNING SCREEN, NOT OFF A COMMIT.** Two colour
rows quote the browser's own computed values because *"it is not red"* is exactly
the kind of claim this file has been wrong about before (`DEF-CWP-3993` corrected
three such rows; `DEF-CWP-4153` a fourth).

## `CWP-030` · Why is this bill different? (wireframe P16)

| # | Type | What the two pictures show |
|---|---|---|
| 30.1 | `STRUCTURE` | ⛔ **THE DRAWING MAKES THE ANSWER THE HEADING AND THE PRODUCT ASKS THE QUESTION.** The wireframe's H1 is **`Why August cost $3.74 more`** — month and figure, readable before anything else, which is what makes this screen a phone-call deflector. The product's H1 is `Why is this bill different?` and the figure lands in a sentence below it (`This bill cost $3.74 more than last month.`). Nothing is missing; the emphasis is. `DEF-CWP-4211` |
| 30.2 | `STRUCTURE` | ⚠ **THE TWO PANELS HOLD THE SAME FIGURES IN A DIFFERENT ORDER, AND THE PRODUCT'S HAS MORE IN IT.** The drawing's left panel is four reason lines then a ruled **Difference +$3.74**. The product draws the headline sentence, then `Last month (BL-…) $138.44` / `This bill (BL-…) $142.18`, then the ruled **Difference**, then a `WHAT MOVED` section with the four lines. The two bill totals are an ADDITION to the drawing rather than a divergence from it, and they are what let a customer check the subtraction. **Recorded, not filed** |
| 30.3 | `CONTROL` | ⛔ **THE DRAWING'S TWO NEXT STEPS ARE ABSENT.** The wireframe ends the right column with **`Send a reading`** and **`Query this bill`**; the product ends it with the leak sentence and stops. Measured in the browser: `send a reading: 0, query this bill: 0`. **Both destinations are BUILT** — the self-read screen shipped in wave J, the dispute screen in wave I — so this is a screen that explains a bill and offers no way to act on the explanation. `DEF-CWP-4213` |
| 30.4 | `DATA` | ⛔ **NOTHING SAYS WHETHER THE RATE MOVED.** The drawing's right column carries **`Rate per gallon — unchanged`** directly under the usage figures, and the wave O demo script step 1 ends *"rate unchanged"*. Neither the screen NOR the served payload holds any rate: `against_last_year` carries two quantities and a unit. A customer told only that they used more cannot tell whether the price also rose, and the two have different remedies. `DEF-CWP-4212` |
| 30.5 | `FORMAT` | ⛔ **A RISE IS NOT PAINTED AS A RISE.** The drawing puts `+$8.83` and `+$4.29` in brand red and leaves `$0.00` and `−$9.38` black; task O2 states the same rule in words — *"positive in brand red, zero and negative ink"*. The product applies it ONLY to the Difference row. Measured from the browser: the headline rise is **`rgb(236, 48, 19)`** and the component rise `+$8.83` is **`rgb(45, 43, 43)`**. `DEF-CWP-4210` |
| 30.6 | `FORMAT` | ⛔ **BOTH BARS OF THE YEAR CHART READ `Aug`.** The drawing labels them **`Aug 2025`** and **`Aug 2026`**; the product renders a bare month name through the shared `UsageBars`, which is correct on `CWP-033`'s twelve consecutive months and ambiguous here, where the two bars are a year apart and the year is the only thing separating them. `DEF-CWP-4209` |
| 30.7 | `FORMAT` | ⛔ **THE QUANTITIES ARE UNGROUPED.** The panel reads `4171 gal → 4820 gal`; the drawing reads `4,090 → 4,820 gal`. **NOT REFILED** — `DEF-CWP-4168` already names its own surface as *"`CWP-033` and every consumer of `quantity_text`"*, and this is that defect seen from a second screen |
| 30.8 | `COPY` | ⚠ **THE DRAWING WRITES SENTENCES WHERE THE PRODUCT WRITES BUCKET NAMES.** Drawing: *You used more water* · *Trash cart charge unchanged* · *A summer discount ended* · *Lower tax on a smaller sewer share*. Product: *Water used* · *Trash standing charge* · *Water discounts* · *Tax*. **DELIBERATE and already argued in `BillComparison.tsx`'s `reasonWord` docstring** — the amount column already carries a signed figure, so stating the direction again in the label is one fact twice inside a row B14 rule 32 budgets at one. **Recorded as a divergence, not filed** |
| 30.9 | `COPY` | ⚠ **THE WORD `unchanged` IS IN A DIFFERENT COLUMN.** The drawing puts it in the LABEL (*Trash cart charge unchanged*) with `$0.00` as the value; the product's label is *Trash standing charge* and the WORD `unchanged` is the value. The product's reading is the better one — a signed zero is a machine's way of saying nothing moved — and it is the PO's own fourth line either way. **Recorded, not filed** |
| 30.10 | `COPY` | ⚠ **THE RIGHT PANEL'S HEADING IS GENERIC.** Drawing: **`AGAINST LAST AUGUST`**. Product: `Against the same month last year`. On its own this is the correct generalisation of a drawing made for one month — but combined with 30.6 it means **the word "August" appears nowhere on that panel at all**, which is why the two are worth reading together |
| 30.11 | `COPY` | ⚠ **THE DRAWING'S SECOND SENTENCE IS ABSENT.** Drawing: *"A jump like this is usually a leak, a hosepipe or a visitor. **A running toilet can use 4,000 gallons in a month.**"* The product draws only the first. **B14 rule 32 budgets one sentence per section**, so the product is following the later rule and the drawing is the older evidence. **Recorded, resolved in the product's favour** |
| 30.12 | — | ✅ **THE YEAR PANEL DRAWS AT ALL — AND IT DID NOT UNTIL TODAY.** `DEF-CWP-4206`: `bill_comparison_for` asked for a 12-month window from a read that needs 13 months of reach, so `against_last_year` was `[]` on **every bill on every account** and this whole column rendered as nothing. Fixed in this wave; the walkthrough now asserts it draws on the August bill AND is correctly absent on September's, where the meter has not been read yet |
| 30.13 | — | ✅ **THE FOUR REASON LINES ARE REAL ARITHMETIC, PROVED ACROSS THREE BILLS.** Read off the page: `+$8.83 / unchanged / −$9.38 / +$4.29` summing to the printed `+$3.74`; a mirror bill printing `−$8.83 / unchanged / +$9.38 / −$4.29` summing to `−$3.74`; and a bill whose total did NOT move printing `+$5.00 / unchanged / unchanged / −$5.00` summing to `$0.00`. `BR-CWP-046` checked as arithmetic on the printed strings, both sides read off the DOM |
| 30.14 | — | ✅ **THE FIRST BILL OFFERS NO COMPARISON, AND NOT ONE AGAINST ZERO.** *"This is your first bill, so there is nothing to compare it with yet."* — no difference figure and no breakdown anywhere on the page |
| 30.15 | — | ✅ **NO RAW MACHINE DATE ON ANY BRANCH.** Counted across all four bills: **0**. The bar labels go through `Intl`, and this screen's other date-shaped values are bill NUMBERS rather than dates — which is why it escaped the sweep that caught waves F, G, I, L and M, rather than because it was written more carefully |
| 30.16 | — | ⚠ **THE ADDRESS DIFFERS FROM THE DRAWING'S.** Wireframe URL bar: `…/bills/BL-2608-0141/explain`. Product: `…/bills/:number/comparison`. Not worth moving a shipped route for, and recorded so the next reader does not treat the drawing's path as the contract |

## `CWP-036` · Your usage looks high (wireframe P22) — **ONE-SIDED: the screen does not exist**

| # | Type | What the two pictures show |
|---|---|---|
| 36.1 | — | ⚠ **THERE IS NOTHING TO COMPARE, AND THE DRAWING SAYS SO ITSELF.** `wireframes/CWP-036.png` is stamped **`BLOCKED`** in its own header and carries a panel reading *"This alert has no trigger in the product today. The event is declared in the notification catalogue and nothing ever fires it."* It is one of the four screens `unbuiltScreens.ts` excludes from its ten precisely because *"the drawing itself marks [them] deferred or blocked"* — so its absence from that register is correct and is **not** a gap in the record |
| 36.2 | — | ✅ **NO ADDRESS SERVES IT, CHECKED RATHER THAN ASSUMED.** The walkthrough opened `/alerts/high-usage` (the drawing's own URL), `/alerts` and `/usage/high`; all three answer with the portal's not-found branch and **none renders `CWP-036`**. Nobody has half-built it behind a door this run could not see |
| 36.3 | — | ✅ **AND NOTHING FIRES IT.** The account's `attention` list carries one row, `{"kind": "pay"}`, and no usage alert of any kind. `US-CWP-044` TC-2/TC-4 |
| 36.4 | — | ⚠ **WHY IT IS A SCOPE DECISION AND NOT LATE WORK.** Firing this needs a daily or weekly comparison against the account's own history. Pine Hill reads MONTHLY, so on this product the alert could only ever fire at billing time — which is a different statement from the drawing's *"Since 25 August you have used about twice your normal daily amount"*. The drawing's own footnote reaches the same conclusion: *"Drawn because the event already exists in name and needs a decision, not because it is nearly built."* **Recorded, not built** |

## What THIS pass could not see

* **One tenant (`pine-hill`) and one customer login**, on a fixture built for this
  wave. Every figure above is that fixture's; the SHAPE of the screen is what is
  being compared, not the tenant's data.
* **A bill with a RATE VERSION change of its own.** The wave O demo script's step
  3 asks for *"a month where a rate version changed: the rate component is its own
  line from the version that applied"*. The seam buckets by `(service, kind)` and
  **does not split a service's usage into a volume part and a price part** — that
  cross-term attribution is a second finance judgment that was never put to the PO
  and is not taken. So there is no separate rate line to compare against the
  drawing, and 30.4 is the visible consequence rather than a missing case.
* **A bill whose shares do NOT tie out**, which would draw the stated-absence
  branch. `cr068-o-fixture.py` refuses to plant one by design, and
  `test_us_cwp_035_tc3` covers it at the seam.
* **Colour and tier by eye**, as this file's header warns of every pass — except
  the two rows above that quote computed values.
