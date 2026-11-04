# Steps 4 and 5 as built, against the drawings — and the first look at all five together

`NCT-01` · lane **NC5-PHOTOS** · 2026-09-29 · id block `DEF-CUS-7910–7919`

**This lane photographed and reported. It redesigned nothing and fixed nothing**
— the only code it wrote is its own walk,
`10-scripts/nc5_five_step_photographs.mjs`. Everything wrong is FILED.

Photographs: `built-2026-09-29-five-steps/`, thirteen images at 1440 and 1280,
each with its pixel dimensions and the state it shows printed in
`00-README.txt`. Taken in Chromium against a booted stack, signed in as Dana at
Brazos Bend, working on an **isolated clone of the demo database** which was
dropped afterwards. **The Create button was never pressed**, so nothing was
written.

⚠ **`fullPage: true` DOES NOT CAPTURE THIS APP AND EVERY EARLIER SCRIPT USED
IT.** `.app-shell` is `height: 100vh; overflow: hidden` and `.view` is the
`overflow-y: auto` pane inside it, so the document never grows and `fullPage`
returns the fold. These shots grew the VIEWPORT to `.view`'s own scroll height
and print each image's dimensions, so a reader can see two shots differ rather
than take it on trust.

---

## The rail — the thing that was wrong in every stale photograph

**Correct on all five steps, measured, at both widths.** Five cells reading
`Customer · Premise · Units · Charges · Review`, one word each; the sub-line
reads `Step N of 5 · <word>` on every step; the last cell sits `0px` past the
rail and the rail's right edge lines up with the panels to `0px` at 1440 and at
1280. The stale shots showing `Step 3 of 8` and an eight-step rail predate the
build; they do not describe it.

`step3-units.png`'s divergence 8 — *"The photograph shows eight … the step list
belongs to the MODEL lane, which is folding it"* — **is now closed. It is
five.**

---

## Step 4 · Charges — against `step4-charges.png`

**It matches.** The seven-cell context strip, *Who is billed*, *Payment*,
*Billing preferences* and *What is charged* are all there, in the drawn order,
with the drawn fields. Differences, each with why:

| # | The drawing | The built screen, and why |
|---|---|---|
| 1 | A **`QTY`** column drawn as an editable white box holding `3` | **THE COLUMN IS BUILT; THE BOX IS NOT.** `CHARGE · BASIS · QTY · EACH · AMOUNT` is on the screen and `QTY` renders a `CellStatic` count that moves with step 3 — `6`, for six units. `OQ-CUS-12770` decides whether a quantity is TYPED or COUNTED, and `CR-150-BRC09` §5 forbids building the input until the PO rules; the walk asserts **zero editable Qty inputs**. ⚠ **This is worth the PO's eye: showing the counted figure is visible on screen, and a reader could take it as the question already answered.** It is not — nothing types one, and nothing multiplies in the browser. |
| 2 | *Cheque number* | **`Check number`** — PO ruling 2026-09-29, American English. A ruling beats a drawing. |
| 3 | `Amount` | **`Amount taken`**, which is the payments module's own word for the same box. |
| 4 | no clearing date | **A `Clearing date` IS built**, with *"The day the money arrived."* under it (`BR-PAY-021`, the S22 form's own five words). Added rather than dropped, and named here because it is visible. |
| 5 | `Billed to *` | **`Who is billed *`** — the panel heading's own words reused on its one control. |
| 6 | `+ Add charge` | **`+ Charge`** — the rendered catalogue string, two words under B14 rule 33's label cap. |
| 7 | `Remaining, due in {terms} days   $535.00` | **The words are built; the FIGURE is not** — the line reads *"Remaining, due in 30 days · Outstanding shows on the build."* Hard rule 2 keeps arithmetic out of the browser, and `$1,035.00 − $500.00` is arithmetic. The drawn figure is an illustration (rule 37); the drawn SUBTRACTION is not something this screen may do. |
| 8 | *Priced, not posted* once, under the totals | **A `PRICED, NOT POSTED` badge on each money line** — the kit's basis marker, one per figure. Construction, which rule 44 gives to our standard. |
| 9 | The charge picker is a search box with a magnifier | **A `<select>`** carrying the code and the name — `AFTER-HRS · After-hours service call` — 18 codes on the demo estate. |
| 10 | The rationale lines under *Billed to* and *Payment option* (*"Options: …"*) | **NOT BUILT.** Both are rule 33's RATIONALE at zero words on screen, removed rather than shortened. |

---

## Step 5 · Review — against `step5-review.png`

**Three things are right and three are wrong, and two of the three wrong ones
are filed as defects.**

Right: the nine-cell *At a glance* strip (`Customer 1 · Premises 1 · Units 6 ·
Service points 12 · Meters 12 · Sub-meter links — · Plan assignments 6 · Work
orders — · One-time charges $450.00`), the four folded review groups each with
its `Edit`, the *Messages* table with its three rows and `+ Add template`, and
*What Create makes*.

| # | The drawing | The built screen |
|---|---|---|
| 1 | *Messages* appears ONCE and there is no *Who we are telling* panel at all | ⛔ **`DEF-CUS-7910` — BOTH PANELS RENDER TWICE.** `ReviewStep` draws *Who we are telling* and the *Messages* table itself, and `NewConnectWizard` STILL mounts the whole `CommunicationStep` after it, under a comment reading *"until the REVIEW lane draws it there"* — which it now has. **That is hard-won law 2's rotten hold exactly: landing the screen and releasing the thing that was holding its place are two acts, and only the first felt like the work.** Every DOM case passed, because each asks whether a panel is PRESENT and none asks whether it is present ONCE. |
| 2 | The opened *Charges and payment* group shows **`CHARGE · BASIS · QTY · EACH · AMOUNT`** | ⛔ **`DEF-CUS-7911` — the built table has THREE columns.** `EACH` and `AMOUNT` are simply not in its `columns` array, so the review can never show what a charge costs. ⚠ **The component's own docstring two lines above says the opposite** — *"`Each` and `Amount` come from `POST /connections/quote-preview` through the props this component is handed"*. Hard-won law 1: a comment claiming a guarantee is not the guarantee. |
| 3 | *What pressing Create makes* has FIVE columns — `WHAT · HOW MANY · NAMED · WHERE IT SHOWS · WHEN`, with `C-00011`, `AC-2026-00011`, `cheque 4471` in the NAMED column | **FOUR columns — `NAMED` is not built.** Reported rather than filed: the names in it are ids the commit has not issued yet, which is a real reason not to print them, and B14 rule 31 governs what may be shown. **It is a decision somebody should take on purpose rather than a gap nobody noticed**, which is why it is written here. |
| 4 | The red note *"The two shaded rows do not happen today…"* | **DELETED, and correctly** — the invoice IS issued inside the commit and the payment IS recorded. A stated absence that outlives its cause is a lie the product tells about itself. Recorded in `NewConnectReviewStep.tsx`. |
| 5 | Heading *What pressing Create makes* | **`What Create makes`** — three words, rule 33's label cap. |
| 6 | The review group's charge cell reads `CONN · Connection fee` | **The CODE alone — `AFTER-HRS`.** Step 4's own picker shows code and name; the review shows less than the step it summarises. Minor, reported not filed. |
| 7 | Groups drawn with one opened | Built folded; **one press opens it in place**, and `step5-review-group-open-1440.png` is that state, photographed so the two can be compared. |

---

## The other two, re-checked rather than re-litigated

`DIVERGENCES-steps-1-2.md` and `DIVERGENCES-step3.md` were read and **every
stamped divergence in them is still true today**, with two exceptions, both
improvements:

* **`DIVERGENCES-step3.md` divergence 8 is CLOSED** — the stepper ran eight
  when that file was written and runs five now.
* **`DIVERGENCES-steps-1-2.md` §C2's co-applicant note is confirmed by
  photograph**: closed it is half-width beside *Mailing address*, open it takes
  the full width and *Mailing address* moves below it.

Three things visible in these photographs are NOT in either file and are added
here rather than left to be found:

| Where | The drawing | The built screen |
|---|---|---|
| Step 1 · `Account details` | *"Nothing appears if the utility set none up."* | ⛔ **`DEF-CUS-7912` — the HEADING appears anyway.** The `<h4>` sits outside `CustomFieldsInput`, so a utility with no `S18` fields — the demo estate, and most utilities on day one — gets a bold heading over empty space. Its own comment claims *"IT RENDERS NOTHING AT ALL WHEN THE UTILITY DEFINED NONE"*. Law 1 again. |
| Step 1 · `Person or company` | a dropdown | a segmented control. Construction, rule 44; named here because §B of the steps-1-2 file lists the other two control swaps and not this one. |
| Step 2 · `Utility services` | one dropdown reading *Water, Sewer, Trash, Fire, Broadband* | removable chips plus a type-to-filter add control — **B14 rule 9 requires the chips**, so the standard wins (rule 44). The add control's own placeholder reads *"Every service you sell is on this address"* once everything is chosen, which is eight words where rule 33 caps a label at three. Reported, not filed: it is a `<select>`'s placeholder option rather than a label, and that is a judgment for the UI lane. |

---

## One check that does not check, found on the way in

**`DEF-CUS-7913`.** `10-scripts/cr150_new_connect_five_steps_walkthrough.mjs`
§4 is titled *"NOTHING IS LOST — the three absorbed steps' own fields, on
screen"* and asks for `[data-unit-count]`, `[data-unit-service-grid]` and
`[data-from-each-step]`. **The first and third appear in NO file under
`07-frontend/src`. The second appears only in `NewConnectServicesStep.tsx`,
which the five-step wizard mounts nowhere.** Three of its five assertions are
incapable of passing, so the section proves nothing it claims, and nothing in
CI runs the walk, so its three reds have never been read. This lane's walk asks
the same question through `#nc_from`, the service rows,
`[data-array-action="add-work-order"]` and `[data-proposals]` — every one of
which is on the rendered page.

---

## What could NOT be checked, with a number beside it

* **The commit.** Nothing was pressed, so no row reached the database and no
  claim here is about what `commit_connection` does. `po_new_connect_clerk_walk.mjs`
  is the walk that ends in the database, and it is written for the retired
  eight-step model.
* **Services beyond two.** Brazos Bend sells exactly **2** services (electric,
  water), so step 3's tile reads `2 of 2` and every unit carries two service
  points. That is a real count and not an empty screen, but it is not the
  drawing's five, and no shot here shows a five-service premise.
* **Work orders.** `0 will be written` on every shot: no work-order template on
  the demo estate covers electric or water, so `+ Add work order` reaches the
  template search and finds *"No template covers these services."* The search
  opening in place IS proved; a populated work-order row is not.
* **Rendered spacing against the type scale.** No gate in this repo reads
  rendered output and this walk reads the DOM, not the stylesheet. Every
  spacing claim here is an eye on a photograph.
