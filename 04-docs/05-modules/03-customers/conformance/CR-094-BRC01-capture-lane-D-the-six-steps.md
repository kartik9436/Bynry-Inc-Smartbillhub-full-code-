# CR-094-BRC01 capture wave · lane D — the six steps of the New request wizard, rebuilt from the page images

**Screen:** `/{tenant}/requests/new?step=1…6` (`REQ-03`, `ServiceRequestCapturePage.tsx`)
**Date:** 2026-09-15 · **Base:** `801424ed` · **Defect filed:** see §8

---

## 0 · The pages read AS IMAGES, and at what scale

B14 **rule 42** (PO 2026-09-13, *"When you use images to create screens your accuracy is
higher; hence dont create screens using only Text"*). Every screen below was built from
the picture, never from the text layer, never from the measurement document, never from
the existing code.

| Page | Read at | What it settled for this lane |
|---|---|---|
| `p076` | scale 2 | step 1's field order; step 2's `Category`/`Sub-category` pair, the closed services control with its chips, the `SERVICE`/`REQUESTED START` table and `Connection date` beneath it |
| `p077` | scale 2 | step 3 entire — `Street address or premise` + `Unit`, the three absence panels, the red *not refused* panel, `What the register matched` |
| `p078` | scale 2 | step 4's four filter chips and where they sit relative to the attach controls |
| `p079` | scale 2 | step 5's quote and payment summary; step 6 opening in two columns |
| `p080` | scale 2 | **the page this lane leant on hardest** — step 6's right column row by row: `Documents` ✎ Step 4, `Fees` ✎ Step 5 with its five rows and its red sentence, `On submit` ✎ Step 6 with its three |
| `p081` | scale 2 | step 6's footer, and where a captured request lands |

Nothing needed a higher scale; the two dense tables (`p078`'s document table and `p080`'s
message table) are legible at 2.

---

## 1 · The rulings this lane built, in the order they arrived

| Ruling | What it changed here |
|---|---|
| **Services are a multiselect** (PO, *"this should be multi select and only utilityservice activated for this Tenant should be shown"*) | eleven always-open `ServiceCard`s → one `ChipMultiSelect` with a derived count |
| **The address is PICKED, not typed** (PO, *"it means its a search and if not foudn them alow user to add them"*) | step 3's street box searches the premises register; the premises' city, state and ZIP show read-only |
| **`BR-CUS-092` amended — the date of birth and the licence are captured on step 1** (PO, *"ensure user is able to inputs both these on step 1"*) | two stated absences → two live inputs |
| **The customer category returns to step 2** (PO, *"this should be on step 2 as per image"*) | the control AND its completeness gate moved |
| **`BR-CUS-1022` bites on step 1** (exposed by the above; `DEF-CUS-5415`) | `Applying as` returns as the first control, and decides what the step asks for |
| **`BR-CUS-1070` — each service carries its own start** (lane F) | the drawn `SERVICE`/`REQUESTED START` table, built to lane F's published payload |
| **The counter fee POSTS** (PO, *"payemnt should show in payments, in ledge and in fiannce books"*) | the superseded *posts nothing* sentence came off; the card and cheque tender fields went on |
| **Category and Sub-category are DROPDOWNS** (PO, of the built step 2: *"please note on step 2 it is drop down for Category and sub category"*) | the segmented row became a `SelectField`, paired with Sub-category on one row as `p076` draws them |

---

## 2 · Before and after, step by step

### Step 1 · Customer

| Drawn (`p076`) | Before | After |
|---|---|---|
| `Channel *` | built | unchanged |
| `Full name *` · `Email` · `Phone` | built | unchanged |
| `Date of birth`, *if known* | **a stated absence** — *"A date of birth is not recorded on a request yet."* | **a live date input**, bounded at today |
| `Driver's licence` | **a stated absence** — the server's own sentence | **a live input**, masked at step 6, **with the encryption promise beside it** once lane G's column landed |
| `SSN` | built | unchanged, and its `ssnHint` promise is still printed exactly once |
| — | `Customer category` (seven fetched chips) | **gone to step 2**, with its gate, and **as a dropdown** |
| — | — | **`Applying as`, added** — `BR-CUS-1022`, above the identity fields |

**A company is asked for its Tax ID and for nothing of a person's.** `clearOtherKind`
BLANKS the other kind's answers rather than hiding them, because `BR-CUS-1022` says the
evidence is *"refused BY NAME rather than dropped"*.

### Step 2 · Connection

| Drawn (`p076`) | Before | After |
|---|---|---|
| `Category *` — a closed select | on step 1, as a segmented row of seven | **here, as a DROPDOWN, and the gate came with it** |
| `Sub-category` — a closed select beside it | a dropdown, on its own row | **paired with Category on one row**, as drawn |
| `Which services does this property need? *` — one closed control, `N of M selected`, chips beneath | **eleven always-open cards in a three-column grid** — the shape the drawing rejects by name | **`ChipMultiSelect`**, with the drawn count line above it |
| `SERVICE` / `REQUESTED START`, one row per picked service | **missing** | **built**, appearing with the first picked service |
| `Connection date` | built | unchanged, and drawn BENEATH the table as the drawing puts it |

**The denominator is derived and a test asserts it moves.** Measured on the running
product: `brazosbend` reads **`0 of 2 selected`** and **`2 of 2 selected`** after two
picks. In the suite a four-service tenant reads `0 of 4` and an eleven-service tenant
`0 of 11`, from one code path.

### Step 3 · Addresses

| Drawn (`p077`) | Before | After |
|---|---|---|
| `Street address or premise *` | one free-text box labelled *Address* | **a search of the premises register** (`GET /premises/picker`), the typed text still `address_as_given` |
| `Unit, flat or suite` | free text | **a picker** where the premises has units; free text where it has none |
| `City *` · `State *` · `ZIP code *` | missing | **read-only, walked from the picked premises** — *From the premises record* |
| `How many units are on this property?` | missing | **still not asked** (see §5) |
| `Plot or parcel` — drawn as GONE | reappeared on the unresolved branch | **removed; the column stays and stops being written** |
| Billing address + its box | built | unchanged |
| `What the register matched` — `LOOKED FOR`/`MATCHED`/`CONFIDENCE` | missing | **built**, reading lane B's served numbers |
| *"An address that matches nothing is not refused"* | the unresolved branch | **`+ Premises` opens the register's own creator** |

### Step 4 · Documents

Four chips `All · Required · Missing · Rejected` added above the attach controls and
narrowing the list. Measured on the running product: `Required` takes the list from
**9 rows to 0** on a tenant that has ticked nothing — and says so instead of showing an
empty box, because `BR-CUS-095` ships the checklist unticked and an empty list under a
pressed chip reads as a broken screen.

### Step 5 · Fees

* The superseded sentence **came off**: *"These fees are a quote. Nothing here is
  recorded, and nothing here is in the books."* The half that survives is printed —
  **"No invoice and no account yet."**
* **The tender detail, per method and never both at once:** card → last four, brand,
  authorisation code. Cheque → number, bank, date on the cheque.
* **The full card number, the expiry and the security code have no field and no payload
  shape**, and a test asserts their absence by name.

### Step 6 · Check and submit

**Two columns, as drawn.** Left: `The applicant` ✎ Step 1 · `What they are asking for`
✎ Step 2 · `Addresses and property` ✎ Step 3. Right: `Documents` ✎ Step 4 · `Fees`
✎ Step 5 · `On submit` ✎ Step 6.

Rows added to the left column so nothing the clerk typed is invisible: Channel, Applying
as, Date of birth, Driving licence (masked), Tax ID (masked), Sub-category, Requested
start, Connection date, Matched premises, Matched unit, City, State, ZIP, Billing address.

---

## 3 · The wording actually shipped, beside the wording drawn

B14 rule 33 caps an INSTRUCTION at six words per sentence and says *two sentences of six
beat one sentence of twelve*. The drawing's own sentence is 24 words in two.

| Drawn (`p080`) | Shipped |
|---|---|
| *"$105.00 is still owed and this request can still be submitted. The money is not what gates it; the unchecked documents are."* | **"{amount} is still owed. Documents gate this, not money."** |

Two sentences, four and five words. The figure stays a parameter; `$105.00` is an
illustration (rule 37) and, after the ruling that step 5 takes the application fee and
nothing else, a part-paid application fee is the only way an outstanding arises here at
all.

Every other new string is a LABEL (≤ 3 words) or a FACT (≤ 6): *No premises match.* ·
*From the premises record* · *Nothing under this filter.* · *Not numbered yet* ·
*Search the register. Pick the address.* (two sentences of four).

---

## 4 · What was published, and what is still owed to this lane

### Published by this lane

`serviceRequestEndpoints.ts` gains two things, both lane E's contract wired up:

```ts
// GET /premises/picker?q=&per=50  — the register's own search
searchPremisesPicker(q, client) → Paginated<PremisesPickerRow>
//   PremisesPickerRow { id, premise_no, address_line, city, state, postal_code,
//                       units: [{ id, unit_no, label, is_common_area }] }

// POST /service-requests · PATCH /service-requests/{id}
CapturePayload.picked_premises_id?: string | null
CapturePayload.picked_unit_id?: string | null
```

Worked, on `brazosbend`: `q=Willow Bend` → **10 rows**, the first
`P-00002 · 103 Willow Bend Dr`; picking it fills `City Silver Creek · State TX · ZIP
78611` read-only and sends `picked_premises_id`.

### Still owed — two flags, each one line

| Flag | Who | What lands, and the test that fires |
|---|---|---|
| ✅ `IDENTITY_CAPTURE_ACCEPTED` | **lane G — LANDED** | `date_of_birth` and `drivers_licence` are in `CAPTURE_FIELDS`; `drivers_licence_last4` REPLACED them in `IDENTIFIER_FIELDS`, so there is still no `_last4` column of any kind. **The flag is `true` and the payload carries both.** |
| ⛔ `TAX_ID_CAPTURE_ACCEPTED` | **open** | `CAPTURE_FIELDS` has no `tax_id`. `customers.tax_id` exists one table over — a request is not a customer yet. The screen asks for it, reads it back on step 6 and holds it. |
| ⛔ `SERVICE_STARTS_WRITE_PATH_EXISTS` | **lane F** | `POST .../services` takes `{"services":[{"code":"electric","requested_start":"2026-12-05"}]}` as well as bare codes. → *"the per-service write path is HELD"* goes RED |
| ⛔ `TENDER_CAPTURE_ACCEPTED` | **lane H — LANDED ELSEWHERE** | lane H built the tender on `POST .../fee-collection`, not on the capture payload, which is `BR-CUS-090`: the money is taken on the request's own Fees tab so the taker and the reconciler are two people. **`tenderPayload` was reshaped to lane H's nested `{card:{last4,brand,auth_code}}` / `{cheque:{number,bank,date}}`** so the two cannot drift; the flag stays `false` while the WIZARD has nowhere to post it. |

**Each flag is one word.** The screen, the state and the step-6 read-back are built, so
nothing a clerk types is invisible while a flag is `false`; what is held is only the
column it lands in.

⚠ **AND ONE OF THESE HOLDS EXPIRED MID-WAVE, WHICH IS THE WHOLE POINT OF WRITING IT
WITH A TEST.** Lane G landed while this lane was still building. The case asserting
`IDENTITY_CAPTURE_ACCEPTED === false` went RED and named the constant to move — hard-won
law 2's *"when you write a hold, write the test that fires when the hold expires"*, doing
exactly what it is for, inside one session. It split into two cases rather than flipping
whole, because lane G opened two of the three names and not the third.

---

## 5 · What was NOT built, and why — each a decision, not an omission

| Not built | Why |
|---|---|
| **`What goes out to the applicant` and the template picker** (`p080`) | **HELD.** A sibling lane owns the messaging seam; a second messages table here is the thing that seam exists to prevent. **This is the one drawn block on step 6 still absent**, and a test asserts it stays absent. |
| **`How many units are on this property?`** (`p077`) | The brief rules it out — *"it comes from the premises now"*. ⚠ Lane B has since served `location_and_services.units_on_property` as *what the applicant claims*. **The column is served and no control writes it.** Flagged for the orchestrator rather than resolved here. |
| **Step 5's quote LINE TABLE, `Add a fee`, `Waive a line`, `Amount taken`, `Receipt number`** (`p079`) | Outside the brief's scope for this lane; they live on the request's own Fees tab. |
| **`Date of birth` / `Driver's licence` as a rule conflict** | ⚠ **This was the brief's original instruction and it was REVERSED mid-wave by the PO.** The brief said `BR-CUS-092` refused both by name, so the panel should stand. The ruling of this date finishes clause (a) instead. Recorded because a reader meeting the brief alone would build the wrong thing. |
| **`Applying as` is not drawn on `p076`** | B14 rule 41 puts the product at the blueprint's shape, and `BR-CUS-1022` — ruled after the drawing — forbids presenting identity without stating the kind. A signed rule about which evidence may be asked of whom is not a layout question. Recorded in the decision log and in `DEF-CUS-5415`. |
| **`Driving licence` vs the drawn `Driver's licence`** | One word. The catalogue key is used by `ServiceRequestDetailPage` too and re-wording it moves eleven files under a sibling lane. **Reported, not changed.** |

---

## 6 · Proof

| Check | Result |
|---|---|
| `npx tsc --noEmit` | clean — **and proved able to fail first**: a planted `const x: number = "…"` reported `TS2322` at line 3252, then removed |
| `npx eslint … --max-warnings 0` | clean on all three files this lane touched |
| `npx vitest run ServiceRequestCapturePage.test.tsx` | **83 passed** (from 55; 8 rewritten to the new rulings, 20 added) |
| `npx vitest run src/styles/routeBUtilities.test.ts` | **11 passed** — every class in this file compiles through the real Tailwind |
| Locale parity | **+54 / −0 in all eleven catalogues**, through `10-scripts/i18n_fanin.py`; 17,787 → 17,841 each |
| Browser walk, 1440 and 1280 | **74 checks, WALK CLEAN**, against a booted stack |

### Proved RED first (hard-won law 7), in the harness that runs them

**15 of the 21 new DOM/pure cases were run against the tip's own screen** (`2c8161fc`,
the seam constants shimmed so the file compiles) and each failed on the defect it was
written for: *0 of 11 selected* not found ×4, `Street address or premise` not found ×3,
`role="button" name "All"` not found, `[data-review-column="right"]` null, *Not numbered
yet* not found, *No invoice and no account yet.* not found, `Last four digits` not
found, and the three pure functions returning `[]`. The six that passed are the
internal-reference sweep, which is a regression guard and correctly passes on both.

**The match-table case was sabotaged twice, independently:**

| Sabotage | Result |
|---|---|
| prefer the clerk's pick over the server's number | RED — *expected { matched: 'P-00074' } to match { matched: 'P-00052' }* |
| fall back to `resolved_premises_id` when nothing printable remains | RED — *expected '01a0a444-…' not to contain '01a0a444'* |

⚠ **The second sabotage PASSED on the first draft of that case, and finding that is the
point** (law 7: *ask what would make this check pass wrongly*). Three sub-cases each
still had a number, a pick or an address to stop at, so the id was unreachable. A fourth
sub-case — no series, no pick, no address — was added and it is the one that bites. A
related half was also wrong: `expect(null).not.toContain(…)` THROWS rather than passing,
so the assertion is `String(x ?? "")`.

### The walkthrough

`10-scripts/cr094_lane_d_capture_walkthrough.mjs`, run from the repo root. It went RED
three times during this session, each time naming a different real cause — 18 problems
(no sign-in), 10 (a case-sensitive label check and a one-character search term), 0 — so
it is proved capable of failing in the harness that runs it.

⚠ **It also produced a convincing FALSE red worth recording:** the premises picker
answered `404` for three runs and the walk reported *the register said nothing*. The
route was fine; `runserver --noreload` was holding code from before lane E's commit. The
walk now prints the ROW COUNT beside the verdict so a zero is distinguishable from a
silence, and the header names the trap.

### Screenshots

`lane-D-shots/` — `w1440-` and `w1280-` × `step1`, `step1-business`, `step2`,
`step2-picked`, `step3`, `step3-picked`, `step4`, `step4-required`, `step5`,
`step5-card`, `step5-cheque`, `step6`.

---

## 7 · Reds I did not cause, dated

`run_gates.py --changed` reported **7 failing gates. None names a file this lane
touched.**

| Gate | What it names | Dated |
|---|---|---|
| `G98` lint-clean | 11 files — `AccountDetailPage.tsx`, `fixABillSteps.tsx`, `ReadDetailPage.tsx` and eight more | **Reproduced on the UNMODIFIED main checkout at the tip**: `CustomFieldsView`, `formatDate` and `mathLine` unused. None of my three files appears in its list. |
| `G103` holds-cannot-rot | `portal/guest/ApplyForService.tsx` × 3 | portal; untouched by this lane |
| `G105` screen-matches-its-drawing | `CWP-037 footer`, `CWP-041 search` | portal screens |
| `G106` cited-ids-exist | `OQ-CUS-12350/12351` in `customer_edit.py`, and 10 more | backend; `customer_edit.py` landed 2026-09-13 |
| `G107` one-responsive-direction | six portal files + `RunScopeStep.tsx` | portal and billing |
| `G114` list-envelope | `ImportRunListResult` in `endpoints.ts` | a type this lane did not touch |
| `G116` cited-tests-exist | seven backend `Tests:` lines | backend |

---

## 8 · Every function this lane touched in a shared file

Three lanes are live in `apps/customers`, so this list is what an overlap check needs:

* **`07-frontend/src/features/customers/serviceRequestShared.tsx`** — retired
  `UNAVAILABLE.driversLicence`, which lane G's own record asks this lane's commit to
  take. **Nothing read it any more**: the server stopped emitting the code in lane G's
  commit, so a constant pointing at it would make `unavailableReason` answer `null` and
  the screen would print a catalogue sentence saying we hold no licence over the box a
  clerk had just typed one into. Nothing else in the file was touched.
* **`07-frontend/src/features/customers/ServiceRequestDetailPage.test.tsx`** — ONE
  assertion and one added helper (`DEF-CUS-5414`). This is a sibling's file and the edit
  is a single line, made because this lane's label change is what exposed the flaw and
  leaving a red behind would have been worse. See §7.
* **`07-frontend/src/features/customers/serviceRequestEndpoints.ts`** — added
  `PremisesPickerUnit`, `PremisesPickerRow`, `searchPremisesPicker()`, two optional keys
  on `CapturePayload` (`picked_premises_id`, `picked_unit_id`), and one `import type`.
  **Nothing existing was edited or removed.** Lane E's record assigns this hunk here.
* **The eleven locale catalogues** — **+56 / −1 each**, all through `i18n_fanin.py` and
  the repo's own tooling, never by hand. Two existing keys moved and both moves are
  rulings: `applicant.driversLicence` took the drawing's own word, `Driver's licence`
  (B14 rule 41), and `applicant.driversLicenceAbsent` was RETIRED — the sentence it held
  became false when the column landed.
* **`12-governance/10-defect-log.csv`** — one appended row, through `file_defect.py`.
* **No backend file was touched at all.**

⚠ **`DEF-CUS-5391` WAS TAKEN TWICE AND THIS LANE RENUMBERED** (law 11). The allocator
answered `5391` correctly against the world it could see; a sibling had the same number
in flight and pushed first. The register was restored to the tip's exact bytes — the
prefix was proved byte-identical — and the defect re-filed as **`DEF-CUS-5415`**.

### A red this lane DID cause, and what it turned out to be

`ServiceRequestDetailPage.test.tsx` went red on **one** case the moment the licence label
took the drawing's apostrophe: `expect(html).toContain(t(…))` against
`renderToStaticMarkup` output, which escapes `'` to `&#x27;`. **The label was on the
screen and the assertion said it was not.**

**Counted before it was called anything:** the customers suite fails **23** cases at the
unmodified tip and **24** with this lane's work, and the one extra is this. That figure is
how the cause was found rather than guessed — the two failure lists were diffed.

⚠ **It is not a quirk of one string. 574 of the eleven catalogues' English values carry an
apostrophe**, so every `toContain(t(…))` in that file was one copy change away from the
same false red. Filed as **`DEF-CUS-5414`** and fixed with the repo's own `escapeHtml`
shape rather than by bending the copy: the house style is the straight apostrophe (574
straight against 8 curly), and changing a label to suit an assertion is the wrong repair.

---

## 9 · What needs the PO

**Nothing is blocked.** One thing is worth a sentence at the next review, and it is the
only place this lane's screen and the blueprint disagree on purpose:

> Step 1 now asks *"Applying as — a person or a business"* before it asks for a date of
> birth or a licence, and the drawing does not show that question. It is there because a
> company has no date of birth and is never asked for a licence; without the question the
> product would judge a business by evidence it cannot have.

### ⚠ And one difference raised with the PO by the wave lead, NOT resolved here

**The two dropdowns on step 2 are the control type the PO asked for, over the catalogue
we already have — and the drawing's own two values are asking a different question.**

`p076` draws them reading **New connection** and **Residential dwelling**. Ours offer
Residential · Commercial · Industrial · Agricultural · Institutional · Municipal ·
Builder or developer, with `government` greyed beside them, and sub-categories like
Multi-family and Large commercial.

**Those are not the same fact.** The drawing appears to ask **what KIND OF REQUEST this
is**; ours asks **what kind of CUSTOMER this is** — and in this product the kind of
request is the OUTCOME a clerk decides at review (`request.outcome`, one of
`new_connection · move_in · move_out · transfer · disconnect`), which is exactly what
the drawn *New connection* names.

**Nothing about the meaning or the source was changed to make the control type fit.**
The options are still `GET /service-requests/categories` — the Settings catalogue,
never a hardcoded pair — and `BR-CUS-094`'s legacy handling is untouched. The
difference is recorded here so it is visible rather than silently resolved; the wave
lead has it with the PO.
