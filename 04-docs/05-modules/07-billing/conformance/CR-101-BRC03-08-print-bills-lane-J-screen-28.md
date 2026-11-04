# §08 Print bills — screen 28, built as drawn (CR-101-BRC03, lane J)

**Closes `DEF-BIL-5354`.** Files `DEF-BIL-5374`, `DEF-BIL-5375`, `DEF-BIL-5380`.
Built 2026-09-15 against `05-prototype/04 Billing, As Built.pdf`.

---

## 0 · What I read, as images, and at what scale

**B14 rule 42 — a screen is built from the drawing AS AN IMAGE.** Read with the
Read tool, never from a text layer:

| page | what is on it | scale |
|---|---|---|
| **p147** | §08 opens: the cost table (0.012 s a bill · 6 pages a bill · 25,000 ceiling), what comes out of the archive, and the red band about the post it cannot claim | 2 |
| **p148** | **screen 28 itself** — the header, the four tiles, group 1 and the top of group 2 | 2, then **4** (cropped, the lower 40% of the page, for the form and the toolbar) |
| **p149** | the table's rows, the pager, the held-back door, group 3, the footer bar, and the eight notes beneath the screen | 2, then **4** (cropped, the upper 30%) |
| **p150** | the last two notes, and the start of screen **28.1 Held back** | 2 |

§09 begins at p151 and nothing from p151 onward was read or built.
The crops were rendered with the sibling lane's `crop_render.py` in the session
scratchpad rather than a second copy of it — `10-scripts/pdf/pdf_render.py`
renders whole pages and the toolbar needed the detail.

---

## 1 · Before and after, in one line each

**Before:** one scope select over bill runs, a rollup sentence, a summary panel
and four long vendor paragraphs. 430 lines. A clerk asked *"is Mrs Alvarez's
bill in this set?"* could only generate the archive and open the zip.

**After:** the drawn screen — four tiles, a six-field scope group, a searchable
server-paged table of the period's bills with the hold reason on the row and a
live door to the held ones, and group 3's three claims.

---

## 2 · What the server does now that it did not

| | |
|---|---|
| `GET /billing/print-sets` | also answers `will_print`, `held_back`, `held_reasons[]`, `held_reasons_complete`, `pages`, `pages_per_bill` |
| `GET /billing/print-sets/bills` | **new** — the period's bills, one page at a time, each with `will_print`, `hold_reason` and `pages` |
| `print_set.forecast_print_set` | four COUNTs over the archive's own selection. **Measured on the demo tenant: 4 statements, 0.026 s**, flat at 40,000 bills as at 79 |
| `print_set.forecast_rows` | a page's verdicts in **ONE** statement (measured, asserted in the test) |
| `customers.selectors.account_ids_without_mailing_address` | the address question for a whole selection, as a lazy queryset, through the seam that already existed |

**Three of the eight hold reasons are forecastable and five are not**, and that
split is the design: `_add_one` checks the bill number, the filename collision
and the address BEFORE it draws a page, and everything at or below the draw —
a refused document, a kept original that will not read back, a page count that
cannot be taken — is only knowable by drawing it. `duplicate_filename` is not
forecast either, because `uq_invoices_no` makes two bills with one number
impossible. `held-back.csv` inside the archive remains the record of all eight.

---

## 3 · The figure that moved: 6 pages a bill → **2**, measured

The blueprint's PAGES tile reads *"~2,424 · 6 a bill, measured"*. **B14 rule 37
says a drawn figure is an illustration.** So it was measured instead: every one
of the demo utility's **79 printable bills** was counted through `_page_for` —
the archive's own call — on 2026-09-15, and **all 79 came back 2 pages**, at
0.0047 s a bill. `MEASURED_PAGES_PER_BILL = 2` carries that measurement and the
instruction to re-run it when the bill layout changes.

⚠ **A FIXTURE BILL IS NOT A REAL BILL, AND THE TEST SAYS SO.** A synthetic test
bill with a two-field payload draws in **1** page. So the test asserts the
constant against the renderer within **one page** rather than exactly, and names
that tolerance as the weakness it is: it cannot catch the layout gaining exactly
one page, and only a re-measurement on real bills can.

---

## 4 · Where the drawing and a signed rule disagreed — every divergence, numbered

Nine, each with what was drawn, what was built and the rule that decided it.

**D1 · The status filter is not offered.** Drawn in the toolbar (p148). A print
set is issued and paid bills always (`print_set.PRINTABLE_STATUSES`) and
`print_set_selection` drops a `status` filter deliberately, so the control would
promise a narrowing the server overrides. `test_a_status_filter_is_dropped_
because_the_selection_overrides_it` holds the server half.

**D2 · Route and service are not offered either.** Drawn beside Status. Neither
is in `selectors.INVOICE_FILTERS` — not for this screen and not for the bills
list — so there is nothing to send. **They are a HOLD with a test that fires
when it expires**: `test_route_and_service_are_drawn_filters_that_no_list_serves`
goes RED the day either lands and names this screen by path. Adding them
server-side was the alternative and it was refused as scope: it would mean a
second filter path over invoices, in a shared selector this lane does not own,
that could disagree with the bills list's.

**D3 · `Period from` / `Period to` are labelled `Issued from` / `Issued to`.**
The server's window is `issued_from`/`issued_to` — the day the bill was ISSUED.
A bill's service period is a different pair of dates and nothing filters on
them. A control labelled *Period* that narrows by issue date answers *"is this
customer's bill in the set"* WRONGLY, which is the one question this screen
exists to answer, so the label follows the filter.

**D4 · The manifest format is a FACT, not a picker.** One format is registered,
so a picker is a control with a single option — content a clerk reads for no
decision (B14 rule 32), which is what `print_api.py`'s own note has said since
the registry was written. The field is still SHOWN, with the drawing's warning
line *"One format is registered today."*, because what the vendor receives is
worth knowing before it is handed over.

**D5 · The bill layout is a FACT too, and its words changed.** Drawn as
*"Default — your live template"*. A reprint renders the version PINNED at issue,
for ever (`BR-BIL-026`), so both the picker and those words would have been
false. It reads **"Each bill's pinned layout"**.

**D6 · The `Past print sets` button is not drawn.** Nothing records a print set
after it is handed over — the archive is a job artefact fetched by job id — so
the door would open on nothing. `DEF-BIL-5374` carries what recording one would
take; the absence is stated in group 3 as *"Past sets · Not recorded after
hand-over."*

**D7 · `See the 8 held back →` narrows this table instead of opening 28.1.**
Screen 28.1 with its eight named reasons is `DEF-BIL-5375` and is not built; a
door onto an unbuilt screen is the dead control this repo bleeds from. The
arrow is dropped with it, because B14's button grammar gives `→` to something
that NAVIGATES. Pressing it filters in place and the button becomes
*"Show all bills"*, so it is not a one-way door.

**D8 · Three headings were shortened to three words.** *"THE BILLS IN THIS
PERIOD"* → **Bills this period**; *"WHAT THIS ARCHIVE DOES NOT CLAIM"* →
**Not claimed here**. B14 rule 33 caps a heading at three words, and the repo's
own precedent is a sibling lane doing exactly this on the budget-asks screen
four days ago. *"WHAT TO PRINT"* was already three.

**D9 · Two drawn sentences are not on screen, and one was cut down.** *"The
period picker is the only new thing here. The server already accepts a cycle
filter; nothing ever offered one."* is an annotation to the reader of the
document. *"Said out loud because a mail house assumes otherwise, and a silence
is a claim."* is RATIONALE, which rule 33 gives **zero words on screen** — it
lives in `print_api.py`'s own header instead. *"Search it before you generate —
the question is usually about one customer's bill."* keeps its instruction and
loses its reason: **"Search it before you generate."** (5 words).

**Two more, found by putting the capture beside the page rather than by any
check:** the tiles were built BELOW group 1 and p148 draws them above it, so
they moved; and the account cell was built as a stacked pair and p149 draws
`100377 · Ridge Coffee Co.` on ONE line, which also halves the height of every
row in a fifty-row table.

**And one thing the drawing shows that is deliberately absent: the `↓` export
glyph** beside the column selector. This list has no CSV of its own and an
export that exports nothing is a dead control; the archive IS the export.

---

## 5 · The copy a clerk reads, in full

* Title **Print bills**, subtitle *"Every issued bill · nothing generated yet"*
* Group 1 **What to print** — Scope · Cycle · Issued from · Issued to ·
  Manifest format (*Standard CSV — 14 columns*) · Bill layout (*Each bill's
  pinned layout*) · *"One format is registered today."* ·
  *"Or scope it by:"* + a bill run + **Every issued bill**
* Tiles — **WILL PRINT** 79 *about a second* · **HELD BACK** 0 *nothing held
  back* · **PAGES** ~158 *2 a bill, measured* · **IN THIS PERIOD** 79
  *79 + 0, always*
* Group 2 **Bills this period** — *"Search it before you generate."*, search
  placeholder *"Search bill, account or address…"*, columns **BILL · ACCOUNT ·
  PERIOD · AMOUNT · PAGES · WILL IT PRINT**, verdicts *Will print* and
  *Held · address incomplete*, `1–50 of 79`, **See the 0 held back** /
  **Show all bills** + *"Also in the archive."*
* Group 3 **Not claimed here** — *Addresses · Not CASS-certified, not
  NCOA-processed, not barcoded* · *This screen · Changes no address. No form, no
  save.* · *Past sets · Not recorded after hand-over.* · a CLOSED disclosure
  **Before you send this** holding the server's four sentences verbatim
* Footer *"Runs in the background. Produces one archive."* · primary
  **Generate the print set**

⚠ **A copy defect the browser walk found and the tests could not:** the seconds
tile read **"about 1 seconds"**. `{{seconds}}` is not i18next's `count`, so
nothing was ever going to pluralise it. One gets its own sentence now — *"about
a second"* — in all eleven languages, and the test asserts it.

---

## 6 · The proof

| what | result |
|---|---|
| `npx tsc --noEmit` | clean — **and proved able to fail**: it reported `TS2322 … Type 'undefined' is not assignable to type 'number'` on the preview fixture before the fixture was updated |
| `npx vitest` — `PrintBillsPage.test.tsx` (12) + `PrintBillsPage.dom.test.tsx` (9) + `styles/routeBUtilities.test.ts` (11) | **32 passed** |
| `pytest tests/test_cr101_print_bills.py` | **12 passed** (`JOBS_EAGER=false --reuse-db`, 16 s) |
| `pytest tests/test_cr053_print_set.py` | **28 passed** — the existing suite over the changed `print_set_selection` signature |
| `run_gates.py --changed` | `G107` named this screen's `md:grid-cols-2` and it was fixed to a desktop-first `grid-cols-2 max-md:grid-cols-1`; G107 then PASSES and names nothing here. The other 47 failures are dated in the lane report and none names a file this lane touched |
| browser, **1440 and 1280** | `10-scripts/cr101_print_bills_walkthrough.mjs` — four tiles present and adding up, six columns in the drawn order, `1–50 of 79` from the database, no id, no reason code, money at two decimals, no horizontal scroll at either width |

**RED PROVED FIRST, in the harness that runs it:**

* **frontend** — `holdText` made to return the raw code: the DOM case failed with
  *"Unable to find an element with the text: Held · address incomplete"*.
  ⚠ And worth knowing: `internalReferencesInMarkup` did **not** fire on
  `address_incomplete` — it is neither a uuid nor a dotted identifier — so the
  reason-words assertion is the check that catches a leaked code, not that one.
* **backend** — the address leg removed from `forecast_print_set`: three cases
  failed, the one that matters with
  `assert 0 == 1 … forecast.held=0 … PrintSetResult(… held=[HeldBill(…)])`,
  i.e. the tile said nothing was held while the archive held a bill.

---

## 7 · The demo tenant, measured — and the state that had to be seeded

**79 printable bills, all in cycle `CY-001`, every one with a complete mailing
address.** So the drawn *"8 held back, each with a reason"* had **no real row**,
and the held state was seeded **through the product**: `PATCH /accounts/{id}/
mailing-address` with an empty city — the route the account screen posts to —
which held that account's two bills, and the city was **put back in the same
pass** (`SEED_HELD=1` in the walkthrough). The tiles then read **77 + 2 = 79**
and the rows read *Held · address incomplete* with a dash for pages.

The demo tenant is back as it was: `PrintSetForecast(bills=79, will_print=79,
held=0)`.

---

## 8 · What is NOT built, and where it is routed

* **Screen 28.1 `Held back`** — the eight reasons, what each means, whose job it
  is, and the held bills with a link out to the premises: `DEF-BIL-5375`.
* **A record of past print sets** — `DEF-BIL-5374`.
* **The 6-second broker probe** in front of the tiles — `DEF-BIL-5380`, with the
  measurement.
* **Route and service filters** — D2 above, held with a test that fires.
