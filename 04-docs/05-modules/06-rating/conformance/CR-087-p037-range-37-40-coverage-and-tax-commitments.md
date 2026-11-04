# Pages 37–40 — WHAT IS DRAWN THERE, WHO OWNS IT, AND THE FOUR TAX COMMITMENT CARDS

**Range read:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, **pages
37, 38, 39 and 40**, reported unowned between the Taxes lane (which stopped at
page 36) and the Rate schedules lane (which began at page 41).

**Finding: the range is NOT unowned. All four pages are already covered**, by
three conformance files that were pushed while this read was being set up. Every
page was rendered and looked at before saying so, and each existing file was
checked against the picture rather than against its own filename.

This file exists so the range is not read a fourth time, and it carries the one
thing none of the three transcribes: **the four commitment cards, verbatim.**

---

## 1 · WHAT IS ACTUALLY DRAWN ON THESE FOUR PAGES

| page | what is on it | owner |
|---|---|---|
| **37** | the tail of tax screen `12 · View · Audit` — the `NOT WORKED OUT YET` bar, the `Audit` panel with its four-column version table, the `DATED` callout — then that screen's `FOR` · `HOW YOU GET HERE` · `PRIMARY ACTION` · `WHAT CHANGED` · `STATES` · `COMPONENTS` blocks | `CR-087-p036-tax-audit.md` |
| **38** | the last of the `RULES` sentence and the route-correction line, then **`Commitments in this section`** — the cards `PRB-05`, `PRB-06` and the head of `PRB-07` | `CR-087-p030-tax-overview.md` §12 · `CR-087-p122-specification-register.md` — **and §3 below** |
| **39** | the rest of `PRB-07`, the card `PRB-23`, then the section rule and the **`03 RATE SCHEDULES`** opener, then screen `13 · Create · Step 1 · Basics`'s head, route and `What was wrong` block | cards: as above · opener and screen head: `CR-087-p041-create-step1-basics.md` |
| **40** | screen 13's **whole drawn frame** — kicker, title, sub-line, `Cancel` / `Save draft & exit`, the five-step rail, the `Basics` panel's four fields, the footer — and the `FOR` line under it | `CR-087-p041-create-step1-basics.md` |

**Nothing on these four pages is a list screen.** The Taxes and Discounts lanes
each reported that their sections draw no list frame; that is still true here —
pages 37–40 hold a detail tab, four commitment cards, a section opener and a
wizard step.

## 2 · THE TWO OWNING FILES, CHECKED AGAINST THE RENDERED PAGES

* **`CR-087-p036-tax-audit.md`** declares pages 36–38 and inventories page 37
  correctly: the four column headers `EFFECTIVE · RATE · WHY IT CHANGED · BY`,
  both drawn rows, the `DATED` kicker and its two-sentence body, both STATES and
  the three components `Panel` · `VersionTable` · `Callout dated`. It also
  carries the diff, including that `VersionTable` exists nowhere in
  `07-frontend/src` and that `DatedBanner` renders the drawn KICKER with a
  different sentence. **Nothing on page 37 is missing from it.**
* **`CR-087-p041-create-step1-basics.md`** declares pages 39–42 and says so in
  its own opening: *"THIS FILE COVERS A SCREEN WHOSE FRAME IS ON PAGE 40, ONE
  PAGE BEFORE THIS RANGE."* Its §3 matches the render field for field — all four
  labels, all four help lines verbatim, the three asterisks and the one field
  without one, the two locked selects, the five rail steps and the lone
  `Continue`. **Screen 13 is read, and read properly.** The premise that it was
  unread was true when the range was handed out and stopped being true when that
  lane pushed.

**So there is no fourth file for screen 13, deliberately.** Writing one would be
the duplicate that file explicitly warns about.

## 3 · THE FOUR COMMITMENT CARDS — VERBATIM, WHICH NOTHING ELSE HOLDS

`CR-087-p030-tax-overview.md` §12 gives each card a verdict and
`CR-087-p122-specification-register.md` gives each a register row; neither
transcribes what the cards say. The frame's own instruction is *"Each card names
what the work waits on and what a person would be able to do once it is done.
Nothing outside a card is undertaken."*

**All four carry the chip `UNVERIFIED`.**

### `PRB-05` · The premises count narrows on class and service, not just the boundary
* **Waits on:** *"Two more parameters on `GET /taxes/matched-premises`, which
  takes `premises_scope_kind` and `premises_scope_value` and nothing else."*
* **Screens:** `07` · `09` · `10`
* **What done looks like on screen:** *"A clerk sets the boundary to
  'Everywhere', ticks Commercial only, and the count falls from 1,284 premises
  to 212 before they leave the step."*

### `PRB-06` · What one tax is charged on, and what it collected
* **Waits on:** *"Two reads over invoice tax lines. The remittance worksheet
  DEF-385 names is the consumer."*
* **Screens:** `10`
* **What done looks like on screen:** *"The State Utility Tax page reads
  'Taxable base $38,204.16 · collected $2,387.76' for last month, where both
  tiles currently say nothing totals them."*

### `PRB-07` · The remittance worksheet
* **Waits on:** *"DEF-385 filed it and its own suggested fix says the columns
  and the worksheet ship together. The columns shipped; the worksheet did not."*
* **Screens:** `10`
* **What done looks like on screen:** *"A bookkeeper opens Finance, picks Texas
  Comptroller and August, and gets a worksheet reading '$2,387.76 collected ·
  $11.94 allowance kept · $2,375.82 to remit on form 01-339 by 20 September'."*

### `PRB-23` · Waivers granted and exemption certificates are recorded
* **Waits on:** *"Neither half of the count can be worked out because neither is
  stored. DEF-383 built the exemption CATEGORY object; the certificates and the
  waivers are the other half."*
* **Screens:** `37` · `10`
* **What done looks like on screen:** *"The plan's page reads '3 waivers granted
  · 11 accounts hold a certificate, 2 expiring within 60 days'."*

⚠ **B14 rule 37 APPLIES TO A COMMITMENT CARD AS MUCH AS TO A FRAME.** `1,284`,
`212`, `$38,204.16`, `$2,387.76`, `$11.94`, `$2,375.82`, `3 waivers`, `11
accounts`, `form 01-339` and `20 September` are ILLUSTRATIONS of the SHAPE of a
finished sentence. **No test may assert one, and no fixture may be seeded from
one** — a card is an acceptance sentence, not a data specification.

## 4 · THE CARDS RE-VERIFIED AT 2.234.19 — the sibling's verdicts, spot-checked

`CR-087-p030-tax-overview.md` §12 already re-verified all four. Two were
re-checked here independently and both hold:

* **`PRB-05` is BUILT.** `06-backend/apps/rating/api.py:476–484` passes
  `customer_classes` and `services` into `selectors.matched_premises` beside the
  two scope parameters the card says are the only ones. The card is stale.
* **`PRB-23` is HALF BUILT.** `06-backend/apps/rating/selectors.py:2903–2905`
  serves `exemption_category_count`; nothing counts certificates or waivers,
  which is the half the card says is unstored. The card is accurate.

`PRB-06` and `PRB-07` are recorded NOT BUILT by that file, with the tile and the
refusal sentence named; nothing found here contradicts it.

## 5 · ONE THING WORTH SAYING ABOUT THE RANGE ITSELF

**A blueprint section does not end where its screens end.** Both range gaps
reported so far — this one and the charge-code one at pages 2–10 — are the same
shape: a lane's range was cut at a SCREEN boundary while the document's own
boundary is a SECTION, and the material that falls between them is the section
opener at the front and the commitment cards at the back. Those are the two
places the document states what is undertaken and what is not, so they are the
parts a screen-by-screen read is most likely to drop and least able to do
without. **A range handed to a lane should start at a section rule and end at
one.**
