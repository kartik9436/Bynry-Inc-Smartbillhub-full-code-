# Capture steps 1 and 3, built to the drawing — and the one place the drawing lost

**Built at:** `v2.311.2` · 2026-09-19
**Benchmark:** `05-prototype/02 Accounts Menu Blueprint.pdf`, entry **06 Service request
capture**, **pages 75, 76 and 77**, read **AS PAGE IMAGES** at scale 2 and scale 5
(B14 rule 42 — *"When you use images to create screens your accuracy is higher; hence
dont create screens using only Text"*).
**Scope:** steps **1** and **3** of `ServiceRequestCapturePage.tsx`. Steps 2, 4, 5 and 6
were not touched.

⚠ **THE BLUEPRINT IS ON THE WORKING BRANCH, NOT ON THE DEFAULT ONE.** `CLAUDE.md` tells
lanes the PDFs live on the default branch; for Accounts that is wrong, and a lane that
checked only `origin/HEAD` would have found nothing and fallen back to `r10`. Check every
ref: `git ls-tree -r --name-only <ref> | grep -i 'pdf$'`.

⚠ **THE SCREEN TITLES AND FIELD LABELS ARE NOT IN THE PDF'S TEXT LAYER AT ALL.**
`Addresses`, `Check and submit`, `City`, `ZIP code` — every one is drawn as vector art.
A text search returns nothing and would report that these screens are not in the document.

---

## 1 · What was built

### Step 1 · Customer (p075 head, p076 fields)

| Drawn | Before | Now |
|---|---|---|
| `Channel` (dropdown) | labelled *How did this reach us?* | **`Channel`**, in all eleven catalogues |
| two columns: `Channel` · `Full name *` / `Email` · `Phone` / `Date of birth` · `Driver's licence` / `SSN` | a **three**-across grid — Phone sat beside Email on row one and every field after it moved | **two across, in the drawn order and the drawn pairing** |
| no help under `Full name` | 16 words of rationale, and a second sentence on a staff channel | **gone** — the asterisk appears and disappears with the channel, which is what those sentences said |
| `if known` inside the date box | a help line reading *If known* | **gone** — see §3, the placeholder cannot be built |
| no help under the licence | *Stored encrypted. Last four shown.* | **gone** (B14 rule 33 — rationale is zero words on screen) |
| no help under the SSN | *Stored encrypted and shown to staff as the last four digits only.* | **gone**, same rule |
| one checkbox `Add a co-applicant` | a `Co-applicant` heading, an `Optional · contact only` pill, a 26-word note, its own `Panel` | **one checkbox**, in the same block as the fields |

### Step 3 · Addresses (p077)

| Drawn | Before | Now |
|---|---|---|
| `Street address or premise *` · `Unit, flat or suite` | built | unchanged |
| `City *` · `State *` · `ZIP code *` | shown only after a pick, three across | **two across in the drawn position** — still walked and read-only; **see §2** |
| `The property` → `How many units are on this property?` + *What the applicant says is there.* | **absent entirely** | **built**, editable, reaching `units_on_property` |
| ☑ `Billing address same as service`, then a **disabled** `Billing address` box | the box was **hidden** until the tick came off | **drawn and disabled**, with its reason under it |
| `What the register matched` — **three** rows | two rows, and neither could name a unit count | **three**, with `Agrees` / `Differs` |
| **no** `Property details` radios | six radios, each with its own explanation — 84 words | **gone**; `property_type` stays a column |

**Proved by** `10-scripts/po20260919_request_steps_1_and_3_walkthrough.mjs`, in Chromium at
1280 against Django + PostgreSQL on `brazosbend`: **40 PASS, 0 FAIL**, and the same walk
against the 2026-09-15 build reports **12 PASS, 15 FAIL**.

---

## 2 · THE ONE PLACE THE DRAWING LOST — City, State and ZIP

**This lane's brief asked for three editable fields and *"new payload keys"*. They were
not built, and that is a ruling being obeyed rather than a corner being cut.**

* `CLAUDE.md` **hard rule 8** / `BR-MET-1161` — *an address is stored on `premises` and
  NOWHERE else*; everything else derives it by walking.
* **PO ruling 2026-09-15**, verbatim: ***"if we have unit or street address then we should
  take it from premises/Unit - it means its a search and if not foudn them alow user to add
  them"***.
* `service_request_service.CAPTURE_FIELDS` carries the warning **in capitals**:
  `address_city_as_given`, `address_state_as_given` and `address_postal_code_as_given` had a
  model field, a migration, a widened allow list and a fifth `G85` home entry for about an
  hour on 2026-09-15 before the ruling landed. *"Do not re-add them."*
* `BR-CUS-1055` records the near-miss **for exactly this reason**: *"the next lane reading
  five drawn boxes will want to add them again."*

**And the drawing states the absence itself.** p075 says a dashed block IS a stated
absence; p077's caption counts three on this step; and one of the three sits beside these
very boxes, arguing the product's side rather than the wireframe's:

> **THE ADDRESS IS ONE FIELD TODAY, NOT FIVE** — *"The request keeps the address exactly as
> the applicant gave it, in a single line, and never overwrites it with whatever the
> resolver matches. Five boxes are five columns, and the reason there is one is that an
> applicant's address is not a premises yet."*

**What WAS taken from the drawing is the layout**: two across, `City` beside `State`, `ZIP
code` on the row below, directly under the street and unit boxes.

**Nothing was put back to the PO** — hard-won law 13: it was ruled four days ago, in both
the decision log and `BR-CUS-1055`, and re-asking manufactures the inconsistency the law
exists to prevent.

⚠ **THE WALK PINS THIS, SO IT CANNOT BE QUIETLY UNDONE.** *"city/state/ZIP are walked
facts, not a fourth address home"* counts the inputs inside the picked-premises block and
demands **zero**. If somebody makes them editable, that goes red and names the rule.

---

## 3 · Every other divergence, and why

| Drawn | Built | Why |
|---|---|---|
| `if known` as the **placeholder** of the date box | **nothing** | B14 rule 7 is ratified — a date field IS `<input type="date">` — and a native date input **ignores `placeholder`**. **Rule 38**: where the drawing and our UI rules disagree about how a form is BUILT, the UI rules win, the divergence is recorded and nothing is built for it. The field carries no asterisk, which is what *if known* was saying |
| `Applying as` — **not drawn at all** | a dropdown, first on the step | **PO ruling 2026-09-19**, verbatim: ***"we need person or business - make it drop down"***. It was a segmented pair. `BR-CUS-1022` is why the control exists at all (*the kind must be stated where identity is presented*); p076 was drawn before that rule |
| `Channel *` | no asterisk | pre-filled and cannot be empty; the reasoning the screen already carried, unchanged |
| `How many units are on this property? *` | **no asterisk, and no gate** | `_clean_capture` accepts `None`, `canCreateDraft` does not name it, no signed rule makes it blocking — an asterisk would be a promise `Continue` does not keep, over a number the applicant may genuinely not know |
| `6` left-aligned in its box | **right**-aligned | A12 — money/quantity inputs get tabular numerals and right alignment (`.input-num`), and the sibling *"how many units"* field in `AddUnitsWizard` is built the same way. Rule 38 again: construction is the UI rules' |
| `—` inside the disabled billing box | an empty disabled box | an em dash in a wireframe draws *empty*; in `value` it would be a character no clerk typed that the payload then has to strip |
| *"Filled in only when the box above is cleared."* (9 words) | **"Filled when the box is cleared."** (6) | B14 rule 33 caps a fact at six words. Same meaning, same verb |
| `SSN` | **`Social Security Number`** | **NOT CHANGED, AND REPORTED.** B19 §2 signed the long form and the key is shared with the step 6 review, which is not this lane's. Three words, so rule 33 is satisfied either way. **A lane that owns step 6 should settle it** |
| no `Capturing for a customer` banner | present | the wizard frame's, not this step's — already recorded as PRODUCT ONLY in `new-request-six-steps-measured.md` |
| `Save & exit` | `Save as draft` | already recorded as Partial in the same file; it saves and does not exit |
| no help under `Street address or premise` | *Search the register. Pick the address.* | **kept deliberately.** It is an INSTRUCTION (3 and 3 words, rule 33 satisfied) and it is load-bearing — it is the only thing that tells a clerk the box is a search rather than a text field |

---

## 4 · What this lane FOUND, dated

**`DEF-CUS-5873` — `pickedRow` was permanently `null`, so the unit picker the 2026-09-15 ruling asked for
never rendered.** Landed 2026-09-15 in `a8b921616` — four days before this lane, dated with
`git log -S 'setPremisesQuery("")'`.

`pickPremises` ends with `setPremisesQuery("")`, which is right: the results list should
close when a row is chosen. But the query key is `["capture-premises-picker", premisesQuery]`,
so emptying the query moves the key to one never fetched, `premisesSearch.data` becomes
`undefined`, and a `pickedRow` looked up inside those results is `null` **on the very next
render, for ever**. The branch that decides whether to draw the register's own unit list
reads `(pickedRow?.units ?? []).length > 0`, so **a clerk who picked `P-00045` — six units
on record — was still handed a free-text box, on every premises, every time.**

Measured in Chromium on `brazosbend` before the fix: `unit control tag: INPUT`.

**Nothing could have caught it.** `tsc` is happy — the optional chain is exactly what you
write for a row that may be absent. The suite is happy — the test that exercises the picker
hands the component its own mocked results and never presses the button that empties the
query. And the screen does not look broken, because the fallback it silently takes is a
perfectly good box. **Hard-won law 2: built, and not wired.**

**Fixed by keeping what `pickPremises` already has in its hand** — the row is the clerk's
choice and outlives the search that found it. Proved on the server rather than on the
screen: the walk now asserts the saved draft's `address_unit_as_given` matches the
register's own series (`SCW-U-041`), not something a clerk typed.

---

## 5 · Proof, and the beta left as it was found

* **`npx tsc --noEmit` clean**, and proved capable of failing first — a planted
  `const __proof: number = "not a number"` was shown to error, then removed.
* **`ServiceRequestCapturePage.test.tsx`: 86 pass**, up from 84. Four cases were rewritten
  to the ruled behaviour (the kind is a `<select>`; the two encryption sentences are off the
  screen) and two were added. The new one was **proved red first**: hardcoding the unit-row
  confidence to `agrees` fails it by name.
* **The browser walk was proved red in the harness that will run it** — 12 PASS / 15 FAIL
  against a `dist/` built from the pinned tip, 40 PASS / 0 FAIL against this one. It carries
  `plan_wizard_seven_walkthrough.mjs`'s staleness refusal, and it prints its findings even
  when a control it types into does not exist.
* **Tier 1 gates: 11 PASS, 7 FAIL — the baseline, unchanged.** The same seven fail at the
  pinned tip: `G7`, `G17`, `G53`, `G61`, `G67`, `G106`, `G113`. None names a file this lane
  touched.
* **The beta holds 8 service requests, as it did before.** The walk saves exactly one draft
  per run, tagged `W1AND3-` in the applicant name, and
  `10-scripts/po20260919_request_steps_purge.py` removes them by that tag and nothing else.
  Four were made while building and all four were purged; the count was read from PostgreSQL
  before (8) and after (8).

---

## 6 · Should this file be split?

**`ServiceRequestCapturePage.tsx` is 3,704 lines and holds all six steps in one array.**
The repo already splits exactly this shape elsewhere — `NewConnectOwnerStep.tsx`,
`NewConnectPremiseStep.tsx`, `NewConnectServicesStep.tsx` and five siblings.

**Yes, and the reason is parallelism rather than tidiness**: four steps remain to be built
against this blueprint and they are queued behind each other today, because every one of
them edits the same `steps` array in the same file. Two lanes on two steps is
`CLAUDE.md` law 11's whole-file collision waiting to happen.

**What it would cost, measured on this lane's own edits:**

* The `steps` array is closed over **`form`, `update`, `draft`, `t`, `translate`,
  `dateFormat`, `client`, `navigate`, `tenantPath`** and twelve query results. Splitting
  means either a props object per step (wide, explicit, and what the `NewConnect*` siblings
  do) or a context. **The siblings' answer is the one to copy.**
* Step 3 additionally closes over `premisesQuery`, `premisesSearch`, `pickedRow`,
  `heldPremises`, `pickPremises`, `pickUnit` and `clearPickedPremises` — a self-contained
  cluster that would move cleanly.
* The **pure functions** (`capturePayload`, `matchRows`, `identityPayload`,
  `serviceStartsPayload`, `filterDocTypes`, `blankOptionalCount`) are already exported and
  already tested separately; they would go to a `captureShared.tsx` and nothing about them
  changes.
* **The test file is 1,900 lines and imports fourteen symbols from the page.** A split
  moves every one of those imports, so the test file is the real blast radius, not the
  component.
* **`route-b-migrated.txt` needs a line per new file** in the same commit, or
  `routeBUtilities.test.ts` goes red.

**Estimate: one lane, one day, touching nothing else — and it must be its own change with
its own proof, never a side effect of a step being built.** It should happen **before** the
next two step lanes are dispatched, not after.
