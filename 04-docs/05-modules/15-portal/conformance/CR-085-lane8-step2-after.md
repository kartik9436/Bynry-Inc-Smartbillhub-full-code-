# CR-085 step 2 lane 8 — what was fixed, and what was left alone

**Routes:** `/usage` `CWP-033` · `/readings` `CWP-034` · `/equipment` `CWP-037` ·
`/requests` `CWP-046` · `/requests/:reference` `CWP-051` · `/ask` `CWP-010` ·
`/ask-a-question` `CWP-054`.
**Step 1 read:** `CR-085-lane8-conformance.md` (same folder) — what was BUILT
against what is DRAWN. This file is what step 2 CHANGED.
**Base:** `56ddf02fa`, 2026-09-11.
**The walkthrough this lane wrote is
`10-scripts/render-checks/cr085-lane8-usage-ask.mjs`** — seven routes at **390
AND 1280**, plus the failed branch of three of them and a fixture pass for the
two facts the live tenant cannot show. §8 records exactly what was run and what
was not, because a conformance file that says *measured* without saying *with
what* is the shape of claim this repo keeps paying for.

---

## 1 · WHAT CHANGED, IN ONE LINE EACH

| Row | What it was | What it is now |
|---|---|---|
| `DEF-CWP-4846` | a failed read on `/usage` returned ABOVE the page header, so the title and the screen id went with the data | `Usage.tsx` composes `PortalScreen` + `PageHeader` and renders both on **every** branch. `Readings.tsx` and `Equipment.tsx` had been repaired by lane 1; what this lane added to those two is R-10's way out |
| `DEF-CWP-4000` | `CWP-033` was the one signed-in screen with **no heading of any kind** — the last `AWAITING_ANOTHER_LANE` entry in the page-head census | kicker `USAGE` + `<h1>` *What you have used*, plus the drawing's own two controls in the head's action row. The census entry is gone |
| `DEF-CWP-4847` | five KPI tiles into a four-column grid, so *Next reading due* sat alone on a second row at 1280 | `kpiColumns(count)` — four columns unless the last row would hold exactly one tile. Five tiles draw 3 + 2 |
| `DEF-CWP-4848` | `CWP-037` never drew `size_class`, and the name stuttered (`Fire Fire service line`) | the server resolves the code to its ratified NAME; the screen draws `Fire service line · 2"` and `Water Meter · 5/8"` |
| `DEF-CWP-4849` | three drawn states short of the drawing | the readings empty state names the first-read date; the equipment empty state carries `Report a problem`; the estimated PHONE card is tinted. **The 1280 table row is still short one signal — see §4** |
| `DEF-CWP-3945` | `ALSO_SHOW_SCREENS` names `usage` and the usage placement went nowhere | `account_usage` serves `attached_answer`, `PortalUsage` carries it, `Usage.tsx` draws the card |
| `DEF-CWP-4168` | a client-grouped `41,208` beside a server-ungrouped `800 kWh` on one row | both screens group through the kit's one formatter. **No digit changes** |
| `DEF-CWP-4172` | the correction sentence printed the wire's ISO date to the customer | it goes through `usePortalDate` like every other date on the screen |
| `DEF-CWP-4850` | the blueprint states `/ask` and `/ask-a-question` render one screen | **recorded as a fault in the drawing. The screens were NOT merged** |

---

## 2 · THE ONE THAT MATTERS MOST, AND WHY

`DEF-CWP-4846` is the R-10 breach with the largest blast radius on these seven
screens, and `/usage` was its worst case because the screen had **no page head
at all** — so a failed read left a customer with one grey sentence, no title,
and nothing in the DOM that any rendered check in this repo selects on.

**It is fixed with lane 1's own components rather than with a fourth opinion
about what a state card looks like.** `PortalScreen({ screen, head, children })`
renders `data-screen` and the head on every branch; `PortalState` is the one
loading/empty/failed card, told apart by its SENTENCE (R-22) and able to carry
the way out beside the message (R-10).

**R-10's way out is a REAL retry, not a button.** `states.tsx` says in its own
docstring why `waysOut` is optional: a required prop would have been satisfied
ten times by a `Try again` wired to nothing, which is `EmptyList`'s
`onCta: () => undefined` defect. Every `Try again` this lane added bumps a
counter that is in the effect's dependency list, so pressing it re-runs the read
that failed.

**R-22 WAS AN UNRATIFIED PROPOSAL IN STEP 1 AND IS RULED NOW, WHICH CHANGES THE
ANSWER.** Step 1 recorded the question and built nothing: the blueprint's
*"three states can never render as the same picture"* reads as a demand for
three designs, and `CWP-033` drew one card with three different sentences in it.
The PO ruled on 2026-09-11 — *"differntiate it using text message"* — so the
sentence IS the differentiator and this screen was already right. What it could
not do is **say which state it is**, so nothing in this repo could check the
rule at all. `PortalState` puts `data-portal-state` on the card; the seven
screens' loading, empty and failed states now differ by sentence AND declare
which they are.

---

## 3 · THE FIRE LINE, WHICH IS A REAL CUSTOMER

CLAUDE.md's fire rule is that **the size class picks the price and the count
multiplies it** — one 2" line is `$12.00`, one 6" line `$60.00` — and a real
utility is being onboarded on fire. `CWP-037` drew the charge and not the size,
so the one row on the screen with money on it was the one row whose figure could
not be checked against anything the screen said.

Two clauses, one cell:

* **the size**: `equipment_on_unit` serves `size_class` as a bare CODE (`FL-2`),
  and B14 rule 32 keeps an internal code off clerk-facing copy — which is why
  the screen drew nothing rather than drawing `FL-2`. `_equipment_row` now
  resolves it through `tenancy_seam.size_class_names`, the **same** call
  `_billed_on` already makes for `CWP-033`'s *your 96 gal cart* sentence. A code
  with no ratified name answers `None`; it never falls back to the code.
* **the stutter**: the cell was `{{service}} {{kind}}` unconditionally, which is
  right for the seed word *Meter* (`DEF-CWP-3991`: two rows at one property both
  reading `Meter`) and wrong for a type the registry already names after its
  service. The live seed's fire type is **`Fire service line`**, so the cell read
  `Fire Fire service line`.

**The composed cell now reads `Fire service line · 2"` and `Water Meter · 5/8"`.**
The ratified vocabulary names every band after its own service (`Water 5/8"`,
`Fire line 2"`) because a settings screen has nothing else saying which service a
band belongs to; here the row already says, so the size's LEADING words are
dropped where the title has already shown them. **Nothing a reader has not
already seen is removed** — that is what keeps this a rendering decision rather
than an edit of the tenant's own words.

⚠ **A SYNONYM IS NOT A STUTTER ANY CHECK CAN SEE.** A tenant whose trash type is
called *Refuse cart* still gets `Trash Refuse cart`: the two words share no
letters. Said out loud rather than left for the next lane to re-derive.

---

## 4 · WHAT WAS NOT FIXED, AND WHY — READ THIS BEFORE CITING A ROW AS CLOSED

| Left | Why |
|---|---|
| **`DEF-CWP-4849` clause 1 at 1280** — the estimated TABLE row still carries two of the drawing's three signals | `MiniTable` owns the `<tr>` and offers `muted` alone, which is grey TEXT — the wrong signal for a row that matters MORE. A tinted row needs one optional tone on that component, and `primitives.tsx` is the frame lane's file this session. The PHONE card is this screen's own markup and carries the tint |
| **`DEF-CWP-4845` residual** — `ErrandCard`'s hint `<p>` still renders when a card has no hint | Lane 1 closed the expensive half (`:where([data-portal]) p { margin-block: 0 }`), so the band is one `gap-2` step rather than 30px. The remaining fix is a conditional `<p>` **inside `primitives.tsx`** |
| **`DEF-CWP-4850`** — `/ask` and `/ask-a-question` are two screens | **The blueprint is wrong and the product is right.** Filed against the RECORD. Which screen `/ask` should serve is the PO's, and no lane should build to screen 54's *"one component behind both"* until it is ruled |
| **the twelve-month axis at 390** | `Jan Feb M… Apr M…` — recorded, not invented. The options are in §6 |
| **`CPB-11`** (a request says when we will reply) on `CWP-046`/`CWP-051`/`CWP-054` | no promised reply date exists in the data at all. It is a commitment to make, not a defect to fix |
| **`CPB-08`'s door — `→ See the whole bill →`** on `CWP-033` | the cost panel still names the bill in WORDS (*From bill BL-2608-000042*) and offers no link. The destination is lane 5's `CWP-028` at `/bills/{number}` and the address and anchor text are a joint decision; it was not on the branch when this lane finished. **Reported, not built** |

---

## 5 · UNITS — CLAUDE.md HARD RULE 3, RE-WALKED

Every consumption figure on `CWP-033` and `CWP-034` carries its unit, at the
number, in the customer's own unit, never converted:

* `CWP-033` — the KPI tiles (`This period` / `Lowest · Feb` / `Monthly average` /
  `Highest · Jul 2025`) each take the unit as a separate `KpiTile` prop so the
  two type sizes cannot drift; the chart axis reads `{{unit}} per month`; every
  bar's `title` carries it; the year card and the comparison sentences carry it;
  the CSV carries it **as a column on every row**, never as a heading.
* `CWP-034` — `800 kWh`, `842 kWh` and so on in the `Used since` column and on
  the phone card. The DIAL figures (`41,208`) correctly carry none: a register
  index is not a consumption.
* **The absence is guarded on the SERVER and checked first.** `used_since_display`
  is `null` exactly when there is no quantity or no unit, and the cell dashes on
  that — the client only re-renders a figure the server has already permitted.

**What changed here is the SEPARATOR and not the digits.** `UnitCell`'s
`formatQuantity` applies the server's own rounding rule (at most two decimals,
half-up, trailing zeros trimmed) before it groups, so `8402` becomes `8,402` and
nothing else moves.

---

## 6 · THE TWELVE-MONTH AXIS AT 390 — THE OPTIONS, NOT A DECISION

At 390 the chart's month labels truncate to
`Jan Feb M… Apr M… Jun Jul A… Sep Oct N… D…`. The bars, the legend and the
estimate note are all legible; the axis is half-legible. **What it should do
instead is a design decision and this lane did not invent one.** The four
options, with what each costs:

1. **Fewer ticks — label every third month.** `Jan · Apr · Jul · Oct`, four
   labels in 350px, every bar still drawn. Cheapest, changes no data, and the
   customer loses the ability to name a middle bar without counting.
2. **Rotate the labels.** All twelve stay readable; the panel grows ~24px taller
   and rotated type is the hardest thing on the page to read on a phone.
3. **A shorter default window on a phone** — six months at 390, twelve at 1280.
   Every label fits and nothing rotates; the screen then shows a DIFFERENT
   amount of history depending on the device, which is a product statement
   rather than a layout one and the `12 months / 24 months` control already in
   the head would disagree with it.
4. **Scroll the chart sideways inside its own container.** Keeps all twelve
   labels at full size; a customer must scroll to see the year, and the drawing's
   own question is *"am I using more than I used to"*, which is a shape you read
   at a glance.

**This lane's reading, offered and not acted on: option 1.** It is the only one
that changes neither the data, the height, nor what the window control means.

---

## 7 · THE NEAR-MISS WORTH MORE THAN ANY OF THE FIXES

**The first draft of the heading fix made the census BLIND instead of RED, and
it looked like a success.**

`PortalScreen` renders `data-screen` at run time from a `screen` prop. So
wrapping a screen's success branch in `<PortalScreen screen="CWP-033">` gives an
**identical DOM** — every runtime selector in every walkthrough still matches —
and removes the literal string `data-screen="CWP-033"` from the SOURCE.

**Three checks in this repo find a portal screen by grepping exactly that
literal:**

| Check | What it does with the file | What losing it would have cost |
|---|---|---|
| `pageHeadCensus.test.ts` `screenFiles()` | decides which files are screens at all | its own negative assertion could not fire — and `usage/Usage.tsx` was the entry that assertion existed for |
| `g100_every_screen_has_a_door.py` `SCREEN_MARK` | decides **which screen a door is on** | `CWP-033` holds the only door in the product to `CWP-034` and `CWP-037`; both would have read as door-less, or the doors would have been attributed to nobody |
| `g103_holds_cannot_rot.py` `DECLARES_SCREEN` | decides which files it scans for expired holds | `CWP-034`'s held *Send a reading* would stop being watched |

**It was caught by a check going green where it should have gone red.** The
census asserts its `AWAITING_ANOTHER_LANE` list in the NEGATIVE precisely so that
landing a head goes red and names the file; it stayed green, and *green where
red was expected* is the only signal that was available. Nothing else in the
repo — `tsc`, 216 portal cases, every gate — could see it.

**The fix is the cheap half and it is stated as the cheap half.** All four files
keep a literal `<div data-screen="CWP-0nn">` on the success branch, exactly as
`bills/BillDetail.tsx` does, and `pageHeadCensus.test.ts` gains a case that fails
the next time a file composes `PortalScreen` and declares no literal. **The
expensive half — teaching all three scanners to read the prop — is a change to
two gates and needs its own red proof; it is NOT done here.**

---

## 8 · WHAT WAS PROVED, AND HOW

* **Every new guard was shown RED first, in the harness that runs it**
  (hard-won law 7, and its 2026-09-04 clause about the wrong entry point).
  The fire stutter's red proof reads, verbatim:
  `expected 'Fire Fire service line' to be 'Fire service line · 2"'`.
* **`vitest` does not typecheck**, so `tsc --noEmit` was run separately and from
  the repo's OWN TypeScript — `npx tsc` fetches a newer compiler that aborts on
  this `tsconfig` with `TS5101` and then reports no type errors at all, which is
  law 7's *incapable of failing* shape.
* **Browser at 390 AND 1280, signed in as `elena@example.test` on `brazosbend`**,
  through `cr085-lane8-usage-ask.mjs` against this lane's OWN dev server and its
  OWN Django (ports 8462 / 8461, the same database as the shared stack, which
  was not restarted, re-seeded or touched). What it read, verbatim:

  | Screen | At both widths |
  |---|---|
  | `/usage` | `h1` = **`What you have used`**, `data-screen="CWP-033"` present, **exactly one** element says the title, nothing scrolls sideways |
  | `/readings` | `h1` = `Readings on your meters`; the empty state reads **`Your first read is due around Oct 1.`** and the duplicate next-read line above it is **`null`** — `DEF-CWP-4849` clause 2, live |
  | `/equipment` | `h1` present, the `← Usage` door live, cells read **`Electric Meter`** and **`Water Meter`** — no stutter |
  | `/ask-a-question` | the `Or ring us` card is **`{present: false}`** on a tenant that publishes no telephone number — `BR-CWP-093`, live, and the case the fix was written for |
  | all seven | `document.documentElement.scrollWidth === window.innerWidth` |

  **And the branch the defect is actually about — every account read answering
  `500`, which is the state nobody walks:**

  | Screen | `h1` | `data-screen` | `data-portal-state` | ways out |
  |---|---|---|---|---|
  | `/usage` | `What you have used` | `CWP-033` | `failed` | `["retry"]` |
  | `/readings` | `Readings on your meters` | `CWP-034` | `failed` | `["retry"]` |
  | `/equipment` | `What is installed at your property` | `CWP-037` | `failed` | `["retry"]` |

  …each with its OWN sentence. That is `DEF-CWP-4846` closed in a browser, with
  R-22's *which state is this* and R-10's *what can I do about it* beside it.
  ⚠ **THE FIRST ATTEMPT AT THIS SECTION NEVER REACHED ITS SUBJECT**: it
  navigated with `waitUntil: "networkidle"`, and with the reads failing the
  screen's own effect retries and the dev server's socket never goes quiet, so
  it timed out at 30s *before* the branch it exists to look at. It waits for the
  state card now.

  **And the fixture pass, which is how the fire row was seen at all.** The live
  tenant records no size class on either of its two meters, so its cells are
  correctly `Electric Meter` and `Water Meter` with nothing after them. Routed
  through a two-row fixture, at 1280:

  ```
  [fixture] equipment cells:  ["Water Meter · 5/8\"", "Fire service line · 2\""]
  [fixture] monthly:          ["No charge", "$12.00"]
  ok  the fire row states its size
  ok  the water meter keeps its service word and states its size
  ok  neither FL-2 nor W-58 is on the glass
  ```

  That is `DEF-CWP-4848`, both clauses, with the `$12.00` beside the `2"` that
  explains it.

⚠ **AND WHAT THAT WALK COULD NOT SEE, WITH THE NUMBER ATTACHED.** The
`brazosbend` account has **no services on its usage payload and no size class on
either of its two meters**, so at both widths the KPI row drew **0 tiles** and
the equipment cells carried **no size**. Every assertion about tiles, columns,
units and the chart axis therefore passed over NOTHING. The first draft of this
walkthrough reported those as `ok`, which is a check that cannot be told apart
from a real pass (`DEF-182`); it prints `VACUOUS` with the tile count now.

⚠ **TWO OF THE THREE RED LINES IN THAT FIRST RUN WERE THE CHECK'S FAULT AND NOT
THE SCREEN'S**, which is worth recording because it is the same class of error
this file keeps naming. `B14 rule 32 — no size-class CODE on the glass` tested
`/\b(FL|W|CART|DUMP|E)-\d/` against the page text and went red on **`W-7001`**
— the ASSET NUMBER, which is exactly the reference `US-CWP-043` TC-5 puts on
screen. A size-class code and an asset number are the same SHAPE; the check now
reads the actual codes off the payload. The other was the 390 column check
firing on a row that correctly has no tiles.

* **`DEF-CWP-4847`'s rule is proved where it CAN be**, and that is said plainly
  rather than implied: `kpiColumns(3|4|5)` and the rendered `grid-cols-3` class
  are asserted in `Usage.dom.test.tsx`; the live tenant cannot draw a KPI row at
  all, so the browser has nothing to say about it.

* **The suites at `6c5a4f5c8`:** 207 of 208 portal cases green across ten files
  (Usage 53 · Readings 29 · Equipment 29 · TrackRequest 25 · Requests 19 and the
  rest), backend **28 passed** over `test_us_cwp_040_usage.py`,
  `test_us_cwp_043_equipment.py`, `CPB-10` and this lane's own file, `eslint`
  clean. ⚠ **The one red in `tsc` is not this lane's:**
  `payments/Fees.dom.test.tsx(281,14): TS2304: Cannot find name 'QUOTE'`, dated
  with `git log -S "QUOTE"` to **`0c85f58ce`, lane 7, 2026-09-11** — reported
  rather than fixed, because it is another lane's file and still in flight.
