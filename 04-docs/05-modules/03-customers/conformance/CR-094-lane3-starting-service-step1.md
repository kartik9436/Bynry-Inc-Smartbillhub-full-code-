# CR-094-BRC01 · step 1 · lane 3 — STARTING SERVICE, as built against as drawn

**Screens 03 · 04 · 05 · 06 · 07 · blueprint pages 60–97, §10 pages 150–206, §12 pages 207–209**
**Written 2026-09-12 · product `2.237.10`, read off the app shell's own footer in a browser**
**Base commit `46c9fac2a`, branch `claude/hi-0jmv62`**

**STEP 1 CLASSIFIES AND FIXES NOTHING.** No product code was changed. What is
below is a measurement, a comparison, and six register rows.

---

## 0 · HOW EVERY FIGURE HERE WAS OBTAINED, AND WHAT IT IS NOT

| what | how |
|---|---|
| the drawings | **rendered as images** at scale 2 from the PDF pinned at `033981d4f`, `sha256` verified to begin `c8d596bb505f5020ce4b9474` |
| the as-built rails, captions, titles, fields and footers | **a real browser at 1440 and 1280**, `10-scripts/cr094_lane3_starting_service_walkthrough.mjs` |
| B14 rules 7 · 32 · 40 | **`getComputedStyle`**, `10-scripts/cr094_lane3_walk_and_measure.mjs` |
| the step lists | the declared source in code **and** the rail the browser painted — both, and they agree |
| the schema facts | `information_schema` and `pg_constraint` on the running PostgreSQL |

⚠ **NO NUMBER IN THIS DOCUMENT COMES FROM THE PDF's TEXT LAYER.** Every digit
in it extracts as `&`. Prose was read from the text layer where it is reliable;
every figure, every step count and every id was read off a rendered page.

⚠ **THE STEP COUNTS WERE READ FROM THE RAIL, NEVER FROM THE URL.** `?step=` is
clamped on four of these five wizards, so asking for step 10 and believing the
answer would have manufactured a tenth step. The walkthrough detects the clamp
and stops. This is the trap the Assets pass paid for once.

### The data

`brazosbend`, seeded by `python3 manage.py seed_demo` (no new seed script was
needed and none was written). Measured with `app.tenant_id` set: **73 accounts ·
131 units · 79 premises · 50 customers · 8 service requests.** The blueprint's
own fixture figure is 72 accounts; the difference is one row and nothing here
turns on it.

### What was seen in a browser, and what was read from the code

**Seen:** every step of screens 03, 04, 05 and 07 — each `?step=` painted, its
rail, caption, title, fields and footer captured at both widths. Screen 06's
step 1, walked and refused.
**Read from the code, not seen:** screen 06's steps 2–6. They cannot be reached
by URL (finding 4) and the walk is gated on a field the blueprint's own drawing
does not show (finding 6), so this lane reached step 1 only. Their field lists
below come from `ServiceRequestCapturePage.tsx` and are marked ⟨code⟩.
**Not walked to a commit anywhere:** nothing was submitted. Step 1 writes no
data.

⚠ **THE BLUEPRINT SAYS *"Not walked."* FOR ALL FIVE OF THESE SCREENS** (pages 66,
75 twice, 86, 97). So every as-built statement below is new evidence rather than
a re-reading of the blueprint's.

---

## 1 · THE FIVE WIZARDS, INVENTORIED

### Screen 03 · New account wizard · `/:tenant/accounts/new` · A1 id **S18**

**AS BUILT — SIX steps.** Declared at `NewAccountWizard.tsx:126`
(`NEW_ACCOUNT_STEP_IDS`), painted as a six-cell rail:

| # | rail label (character for character) | title (`<h2>`) | fields, in the order the component renders them |
|---|---|---|---|
| 1 | `Customer` | *Who is this account for?* | Category (7 radios: `Residential` `Commercial` `Industrial` `Agricultural` `Institutional` `Municipal` `Builder or developer`) · `Full name*` **required** · `Email` · `Phone` · `Date of birth` *(ph `YYYY-MM-DD`)* · `Government ID` · Person/Company (2 radios) · `Street address` · `City` · `State or region` · `Postal code` |
| 2 | `Service address` | *Pick the unit they'll be billed for.* | `Unit*` **required** *(ph `Search an address or unit…`)* · `Service start date*` **required** (`input type=date`) |
| 3 | `Plan` | *The plan this account bills on.* | **none** — one stated absence, *"Waiting on the account plan table"*, summary **`No plan recorded`** |
| 4 | `Billing prefs` | *Billing & communication.* | `Enrol in autopay` · `Preferred language` · `Tax exempt` |
| 5 | `Deposit` | *Deposit & credit.* | **none** — stated absence *"Waiting on the deposit rules"*, summary **`Nothing will be recorded`** |
| 6 | `Review` | *Review and create.* | `Create and activate` / `Save as a draft` (2 radios) |

Header: kicker `New account`, `<h1>` **`Create a first-time customer account.`** —
**the same `<h1>` on all six steps**; the per-step title is an `<h2>`.
Footer: `← Back` · `Continue` on 1–5, `Create & activate ✓` on 6. `Save & exit`
in the page head. **No `Step N of M` caption is rendered at all.**

**AS DRAWN — FIVE steps** (pages 60–65). Rail: `Customer · Service address ·
Account preferences · Deposit · Review`. Caption `Step 1 of 5 · Customer`
present on every frame. `<h1>` **changes per step** (*Create a first-time
customer account.* → *Which unit?* → *Account preferences* → *Deposit* →
*Review*).

> Page 60, verbatim: **"Every drawing below is the wizard as it should be, not
> as it is."**

### Screen 04 · Move-in wizard · `/:tenant/accounts/{accountId}/move-in` · A1 id **S19**

**AS BUILT — FIVE steps.** Declared at `moveShared.tsx:228` (`MOVE_IN_STEPS`),
painted as a five-cell rail:

| # | rail label | title | fields |
|---|---|---|---|
| 1 | `Find unit` | *Which unit are they moving into?* | **no unit control at all** — the unit comes from the account. One absence, `Kept from the last tenancy` |
| 2 | `Customer` | *Who is moving in?* | identical set to screen 03 step 1, same order |
| 3 | `Start & read` | *Start date & initial meter read.* | `Move-in date*` **required** (`input type=date`) · per-meter `Reading` + `The meter could not be read` (3 pairs on the seeded unit). Absences: `Not chosen here`, and a `CHECK` block on the field visit |
| 4 | `Plan & deposit` | *Plan & deposit.* | `Enrol in autopay` · `Preferred language` · `Tax exempt`. Absences: `No plan recorded` · `Nothing will be recorded` · `Cannot be carried` |
| 5 | `Review` | *Confirm move-in.* | none. Absences: `Email — not sent` · `Document — not produced` |

`<h1>` **`New occupant moving into a vacant unit.`** on all five. No caption.
Footer: `Save & exit` · `Park` · `← Back` · `Continue` / `Complete move-in ✓`.
`?step=6..8` clamp to step 5.

**AS DRAWN — SIX steps** (pages 66–74). Rail: `Find unit · Customer · Start &
read · Account preferences · Deposit · Review`, caption `Step N of 6`.

### Screen 05 · Move-in · standalone · `/:tenant/move-ins/new`

**Same component, entered with no account.** The blueprint draws nothing for it
and says so: *"A second address, not a second screen. Same component; step 1
asks for the unit and derives the outgoing account from it, so nothing is
guessed."*

**The one real difference, measured:** step 1 here renders `Vacant unit*`
**required**, a `<select>` (`#mvi_unit`). Screen 04's step 1 renders **no unit
control**. Everything else — rail, `<h1>`, footer, absences — is identical.

### Screen 06 · Service request capture · `/:tenant/requests/new` · A1 id **S85**

**AS BUILT — SIX steps**, and the rail labels match the drawing **exactly**:

| # | rail label | as built |
|---|---|---|
| 1 | `Customer` | *Who is this request for?* · Category (7 radios, **required by `validate()`, unmarked**) · `How did this reach us?` (`select`) · `Full name*` · `Email` · `Phone` · `Social Security Number` · `Add a co-applicant`. Date of birth and Driver's licence are **StatedFacts, not inputs** |
| 2 | `Connection` | ⟨code⟩ category, sub-category, the eleven-service multiselect, per-service requested start |
| 3 | `Addresses & property` | ⟨code⟩ the service address, the unit count, the billing address |
| 4 | `Documents` | ⟨code⟩ the attach path over eight designed types plus *Anything else* |
| 5 | `Fees` | ⟨code⟩ the quote, the collection and the payment summary |
| 6 | `Check & submit` | ⟨code⟩ every field, then `Submit request ✓` |

`<h1>` **`Capture a service request.`** Kicker `NEW SERVICE REQUEST`.
**This is the only one of the five that renders a `Step N of M` caption**, and it
reads: *`Step 1 of 6 · not saved yet — we need the name and the address before
this becomes a request with a number`*.

### Screen 07 · New connect wizard · `/:tenant/connections/new` · A1 id **S87**

**AS BUILT — NINE steps.** Declared at `newConnectShared.tsx:471`
(`NEW_CONNECT_STEPS`), painted as a nine-cell rail:

| # | rail label | title | fields |
|---|---|---|---|
| 1 | `Owner & build` | *Who is asking for this?* | `Owner or developer*` **required** · `Owner type` · `Sub-category` · `Email` · `Phone` |
| 2 | `Scope & mode` | *What are we connecting?* / *How is the work being done?* | 3 scope radios · `Target activation date` (`input type=date`) · `Our crew did it` / `External system`; **`We schedule it` is a DISABLED button** |
| 3 | `Premise` | *The premise* | `Address*` **required** · `Premise type` · `Parcel or GIS reference` · `Read route` |
| 4 | `Units` | *Units* | `Prefix` · `From` · `To` · `Include a common-area unit`; `↑ Upload a unit schedule` **disabled** |
| 5 | `Map services` | *Services available at this premise* | **eleven** service checkboxes — `Electric` `Water` `Gas` `Sewer` `Trash` `Storm water` `Solar` `Broadband` `Thermal / Heat` `Battery` `Fire` |
| 6 | `Plans & work orders` | *Plans* | `All units on` · `Common area on` |
| 7 | `Charges` | *One-time charges* | **no inputs** |
| 8 | `Communication` | *Telling the customer* | **no inputs** |
| 9 | `Review & confirm` | *What happens to each unit* | 4 occupancy radios · the seven-row *What will be created* table |

`<h1>` **`Establish service at a new address`** on all nine (no full stop, unlike
the other four). Caption on every step: *`Step N of 9 · nothing is written until
step 9. Everything below is a draft until you press Create connection.`*
`?step=10` clamps to `Step 9 of 9`.

**AS DRAWN — EIGHT steps** (pages 86–92). Rail: `Owner & scope · Premise · Units
· Map services · Plans & work orders · Charges · Communication · Review &
confirm`. Steps 1 and 2 merge into one.

---

## 2 · AS BUILT versus AS DRAWN

**Where a step count differs, the drawing it was read from is named.**

| screen | as built | as drawn | drawing read | what moves |
|---|---|---|---|---|
| 03 | **6** | **5** | pages 60–65, rail on the frame at `?step=1` (p60) and confirmed on p61–64 | the `Plan` step is deleted; its content becomes a panel on the unit step |
| 04 | **5** | **6** | pages 66–72, rail on the frame at `?step=1` (p66) and on every later frame | `Plan & deposit` becomes `Account preferences`, and a sixth `Deposit` step is inserted before `Review` |
| 05 | 5 (shares 04's) | not drawn | page 75 — prose only | follows 04 |
| 06 | **6** | **6** | pages 75–79, rail on the frame at `?step=1` (p75 foot) | **no count change** — five of the six steps change their CONTENT |
| 07 | **9** | **8** | pages 86–92, rail on the frame at `?step=1` (p86) and on every later frame | steps 1 and 2 merge into `Owner & scope`; the premise step creates the service address |

### The gaps that are not step counts

| # | screen | as built | as drawn | routes |
|---|---|---|---|---|
| a | 03 · 04 · 05 · 07 | **no `Step N of M` caption is rendered** | every frame carries one | BUILD |
| b | 03 | one `<h1>` for all six steps, the step title an `<h2>` | the `<h1>` changes per step | BUILD |
| c | 03 · 04 | the deposit step collects **nothing** | a full deposit — amount, reason, due date, tender, reference, posting and clearing dates, and a *What the customer pays today* box | BUILD — **and the product's refusal is deliberate and registered; it is NOT a defect** |
| d | 04 | step 1 has **no unit control** | *Search for a vacant unit\** with a results table carrying `VACANT SINCE` and `PREVIOUS ACCOUNT` | BUILD |
| e | 05 | step 1 is a `<select>` of vacant units | the same search as 04 | BUILD |
| f | 07 | step 7 `Charges` has **no inputs** | quote lines, a three-way *Who is billed*, tender, reference, amount, dates and a payment summary | BUILD |
| g | 07 | step 8 `Communication` has **no inputs** | a six-row send table with channel, template and timing, plus a template search | BUILD |
| h | 03 · 04 · 06 | no duplicate-customer check anywhere | `R9` / `ACC-S19` flags a customer already on file, on all three | BUILD |
| i | 03 | no company-master picker | `R8` / `ACC-S18` adds one under *Company*, with a review-step check | BUILD |
| j | 03 · 04 | `#dob` is a bare `input type=text`, placeholder `YYYY-MM-DD` | a date control with a `Today` shortcut and the tenant's format | MAINTENANCE — **already owned by `ACC-S4` / `R3`; not filed again here** |

⚠ **THE DRAWN FIGURES ARE ILLUSTRATIONS AND WERE NOT TREATED AS FACTS (B14 rule
37).** Screen 03's step 1 draws a date of birth of `04/11/1988` and its review
draws `04/18/1984`; the postal code is `78704` on step 1 and `78611` on the
review. Two frames of one drawing disagreeing about the same fact is exactly
what rule 37 settles, and neither number is a requirement. **No figure from any
frame is carried into this document as a specification.**

⚠ **AND ONE APPARENT DISAGREEMENT IS NOT ONE.** Screen 03's drawn rail reads
`Service address` at position 2 while the frame's caption reads `Step 2 of 5 ·
Unit` and its `<h1>` reads *Which unit?*. That is not two answers: the product's
own catalogue key `customers.newAccount.step.unit` has the value **`Service
address`**, so the rail label is the real one and `Unit` is the step's id. It is
recorded here so that a step 2 lane does not "fix" a label that is already
right.

---

## 3 · FINDINGS, EACH ROUTED

**The question, once, per finding: _can a user do this task in the product
today?_ No → BUILD. Yes → MAINTENANCE. Ambiguous → DEFECT.**

### F1 · Seven PO rulings behind these five screens reach no file in this repository — `DEF-CUS-5080` · MAINTENANCE (record)

Measured by grepping the whole tree for each quoted fragment. **All seven return
zero files:**

| ruling, verbatim from the blueprint | drives |
|---|---|
| *"after selecting a unit on the service address, there should not be any step to select a plan as plan is already attached on the unit itself. So whenever the unit is selected, show all the details."* | screen 03 losing its plan step |
| *"on the plans and deposit step, change the plans and deposit step to account preferences … and add one more step of deposit into the move in stepper and copy the deposit step also. from the new account."* | screen 04 gaining a sixth step |
| *"merge the first and second step. On the premise step, there should be the premise step and below the address of that premise will service address. Use the same service address fields only."* | screen 07 going nine → eight |
| *"Don't add any account selection there. Just keep the customer kind only. If the user selects company, then ask user to select the associated company master account. where user can search and select it."* | `R8` / `ACC-S18` |
| *"the system should flag if the details were already attached to any of the accounts in the system and should show the details of the customer account with the proper customer details. This is very important scenario."* | `R9` / `ACC-S19` |

(The sixth and seventh are the capture ruling's own clauses — services on the
connection step, a structured service address and a unit count, the plot removed
— quoted in §13 of the blueprint and likewise absent.)

⚠ **AND THE BLUEPRINT ITSELF IS NOT ON THIS BRANCH.** `git ls-tree -r HEAD --
05-prototype/` lists four PDFs and this is not one of them. So on
`claude/hi-0jmv62` these rulings exist in **no readable form at all**.

This is the same class `CR-094` §0 already fixed once as `DEF-CUS-4996`, and the
blueprint says so in its own `ACC-S11` card: *"This ruling is not in the
repository. It exists in this document and in the chat that produced it."*

### F2 · A refusal that was implemented three weeks ago is still asserted by eight surfaces and two decision rows — `DEF-MET-5081` · MAINTENANCE

`OQ-373` is **CLOSED 2026-08-25 → `BR-MET-116`**. `create_owner_account()` is
implemented at `connections.py:3181` and **called by `commit_connection` at
`connections.py:3059–3060`**. Nothing raises: `grep 'NotImplementedError("OQ-373")'`
over `06-backend/apps` returns comments only.

**The running product agrees.** `/brazosbend/connections/new?step=7` reads, on
screen: *"Billed to — The owner's account, created at step 9. The owner captured
at step 1 is given an account number and the whole quote is tagged to it."*

**Still asserting the refusal:** `connections.py:701` (the field docstring —
*"NOTHING FILLS IT AUTOMATICALLY YET … `create_owner_account()` refuses"*, 2,480
lines above the implementation, in the same file) · `connections.py:1698` ·
`metering/migrations/0029_br_met_113_owner_account.py:28` and `:34` ·
`work/api.py:229` · `work/seams/metering_seam.py:318` ·
`tests/test_us_wrk_002_one_destination.py:92` ·
`16-work/10-execution-plan.md:211` · `16-work/08-screen-layouts.md:224` — **and
two rows of `02-decision-log.md` (2026-09-04) that use the false sentence as
evidence**: *"PROVED RATHER THAN ASSUMED: `create_owner_account()` raises
`NotImplementedError("OQ-373")`"*.

**The stated REASON is false twice over, measured on the running database:**

```
accounts.unit_id      is_nullable = YES
ck_accounts_anchored          CHECK (unit_id IS NOT NULL OR premises_id IS NOT NULL)
ck_accounts_regular_has_unit  CHECK (kind <> 'regular' OR unit_id IS NOT NULL)
```

So *"an account must name a UNIT"* is not true of a `master` account and has not
been since 2026-09-01.

⚠ **THE COST IS ALREADY OUTSIDE THE REPOSITORY.** The blueprint read these
comments and drew a clerk-facing refusal on pages 90 and 92 — *"THE PRODUCT WILL
NOT TAG THIS ACCOUNT YET"* — that the product does not make, and flagged it
itself: *"That reason expired on 2026-09-01 and the refusal did not."* It is the
comments that expired, not the product.

**The decision-log rows are NOT edited.** They record what was believed on
2026-09-04 and that history stands; the correction is a new row (§5).

### F3 · The capture's step 1 refuses by pointing at a mark that does not exist — `DEF-CUS-5082` · MAINTENANCE

`ServiceRequestCapturePage.tsx:585` gates the step on
`account_type_code !== ""`. The category group carries **no asterisk, no
`required`, no `aria-required`**; the only starred label on the step is
`Full name*`. Pressing `Continue` with a name typed shows
*"This step isn't finished. Fill in what's marked above, then press Continue
again."* with `[aria-invalid=true]` count **0** and error-class count **0**.

Breaches **B14 rule 10**, and is the exact case `WizardFrame.tsx:914` warns
about in its own comment: *"the generic one is the FALLBACK — true whenever the
unmet condition is a marked field, and **a lie whenever it is not**."*

⚠ **SCREEN 03 IS NOT AFFECTED, AND THAT WAS CHECKED RATHER THAN ASSUMED.**
`NewAccountWizard.tsx:576` gates on `full_name` and the identity shortfall only,
so its identical unmarked category group is correctly optional.

### F4 · The capture is the one wizard of the five whose step is not URL state — `DEF-CUS-5083` · MAINTENANCE

`EP-SHL-03-forms-wizards.md:110` is a rule, not a habit: *"Wizard step | **all
wizards** | A9 routing model (`?step=`) | none (URL state) | int |
system-derived | clamped to reached steps (BR-SHL-018)"*. `MoveInWizard.tsx:229`
and `MoveOutWizard.tsx:197` both cite it verbatim.

Measured: screens 03, 04, 05 and 07 honour `?step=` and clamp. `/requests/new?step=2`
paints **`Step 1 of 6`** — the page reads `useSearchParams` for `?request=`
only (line 394) and holds the step in component state (line 384).

**The blueprint draws six addresses for this wizard that do not exist**
(`?step=1` … `?step=6`, pages 75–79). A link built to any of them lands the
clerk on step 1, and every `toContain` on the href passes.

### F5 · The `NO COMMITMENT` chip is inverted here, and §12's register is four rows short — `DEF-CUS-5084` · MAINTENANCE (record)

Page 2 defines the chip: *"A screen no specification covers carries NO
COMMITMENT — that absence is the finding, not an oversight."*

**Read off the rendered pages:**

* screen **03** carries the chip (page 60) and is named by **three** rows —
  `ACC-S4` (dates), `ACC-S6` (expired holds), `ACC-S18`, whose entire subject is
  that wizard's review step;
* screens **05, 06 and 07** carry **no** chip and are named by **no row at all**.
  The register's Screens column, across all 17 rows, names only screens
  01 · 02 · 03 · 04 · 08 · 10 · 11 · 12 · 13 · 14 · 15.

**So for this lane's five screens the chip is applied exactly backwards.**

**And §12 settles `CR-094` §3b — both of its candidate figures are wrong.** §12
opens *"One row per commitment, no exceptions. Every commitment appears both
here and as a card in the section that owns it"* and holds **17 rows**:
`ACC-S1`–`S10`, `S14`–`S18`, `S20`, `S21`. **`ACC-S11`, `S12`, `S13` and `S19`
exist as cards in §10** (pages 153 and 198) **and in no register row.** The true
count of commitments is **21**; the register lists **17**; the cover's **10** is
the originally minted series, which the register's own sidebar admits
(*"`ACC-S1…ACC-S10` is a series minted for this document"*).

⚠ **THE COUNT HALF IS NOT THIS LANE's TO CLAIM — `CR-094` step 1 lanes 1 AND 2
REACHED IT FIRST, AND ALL THREE AGREE.** Lane 1 settled it as `DEF-GOV-5007` and
corrected `08-screen-layouts.md`; this lane counted the rows independently,
before reading either, and got the same seventeen and the same four homes in
§10. **Three independent counts agreeing is worth more than one**, so it is
recorded rather than deleted — but the count is theirs. **What is this lane's
own is the CHIP INVERSION above**, which is about screens 03, 05, 06 and 07 and
which neither earlier lane could see from its own pages.

### F6 · The capture's step-1 drawing claims to be the as-built and is wrong three ways — `DEF-CUS-5085` · MAINTENANCE (record)

Page 75 says of this flow: *"All 6 screens of this flow, drawn at 1280 and
buildable as drawn. Real app shell, real stepper, real field labels in the order
the component renders them."* Against the running screen:

1. **the drawing omits the customer-category group entirely** — seven radios the
   product renders first and gates the step on, put there by the PO on
   2026-08-25 and quoted in the code at `ServiceRequestCapturePage.tsx:588`:
   *"on this screen - apply as - we need customer categories that we have from
   settings - ehre as drop down"*. A lane building the drawing **deletes a
   control the PO asked for**;
2. **it draws Date of birth and Driver's licence as filled inputs.** Both are
   `StatedFact` in the product (lines 792, 812) because `_clean_capture` refuses
   `dob`, `date_of_birth` and `gov_id_last4` by name. Building the drawing
   rebuilds the dead UI those two code comments exist to prevent, and
   `BR-CUS-092(d)` is quoted there: *"a false security promise over a government
   identifier is worse than an absent one"*;
3. the drawn field order puts `Channel` first; the product puts the category
   group first.

### The BUILD items — every one of them a drawn remedy, none of them a defect

Rows **a–i** of §2. Each is work the drawings specify and the product has not
done; none is filed as a defect, because a screen that has never claimed to do
something is not broken.

---

## 4 · EVERY STATED ABSENCE, QUOTED

⚠ **NONE OF THESE IS FILED AS A DEFECT.** `CR-094` §5(b): *a held control and a
broken control look identical on screen.* Each is a deliberate, registered
refusal, and each is quoted so a step 2 lane can tell them apart.

**Screen 03** — step 3 `No plan recorded`, under the heading *Waiting on the
account plan table*: *"Choosing a plan here, seeing the services and base charges
it brings, and overriding the unit's default all need the table that records an
account's plan. Until it exists, the plan a bill is priced from is the unit's,
and this step changes nothing."* · step 5 `Nothing will be recorded`, under
*Waiting on the deposit rules*: *"The deposit amount is looked up from the plan's
deposit schedule, and that lookup is not built. The server refuses a deposit on
this call…"* · step 1: *"There is no duplicate check on this step. The shared
customer record it would search — and the linking of several accounts to one
customer — needs the customer table, which does not exist yet."* · step 4
*Preferences this account cannot hold* · step 6 *What this create will not
write*.

**Screen 04** — step 1 `Kept from the last tenancy` · step 3 `Not chosen here`
and the field-visit `CHECK`: *"This flow does not wait for the visit, and the
visit does not close it. If the job cannot be created, this still finishes and
the screen says so."* · step 4 `No plan recorded`, `Nothing will be recorded`,
`Cannot be carried` · step 5 `Email — not sent`, `Document — not produced`.

**Screen 06** — step 1 date of birth and driver's licence, each a `StatedFact`
tracking `DEF-638` and `BR-CUS-092`.

**Screen 07** — step 2 `We schedule it` is a disabled button · step 4
`↑ Upload a unit schedule` is disabled · step 7: *"There is no quote on this
build. A quote arrives with an approved service request; opened without one,
this step has nothing to show and nothing is charged at step 9."* and *"Even
with a quote, the total is recorded against the build and raised as an invoice
by nothing yet."* and, on deposits, *"The per-unit deposit policy is not shown
here because this screen cannot read it."* · step 8: *"The message itself cannot
be queued yet: the platform has no message kind for a connection, so a
service-live letter has nowhere to go."* · step 9 `Sub-meter links — Cannot be
created from here — a sub-meter link is an asset record` and `One-time charges —
No quote on this build, so nothing is charged.`

⚠ **AND ONE REFUSAL ON SCREEN 07 IS NOT A HOLD — IT IS A CLAIM THAT EXPIRED**,
and it is finding F2. The screen itself is already correct; the comments behind
it are not.

---

## 5 · WHAT SCREEN 03's `NO COMMITMENT` MEANS FOR IT

The chip's own definition (page 2) is *"If a thing is not in a commitment card,
nobody has undertaken to build it."* Taken at face value it would mean **the new
account wizard — the door every counter sign-up goes through — has nobody
undertaking to build anything on it.**

**That reading is wrong, and F5 is why.** The register names screen 03 in three
rows, one of which (`ACC-S18` / `R8`, pages 192–197) is a full remedy drawn
across six pages for that wizard's own review step. The chip is stale: it was
true when the series was `ACC-S1…ACC-S10` and was not re-walked when the series
grew to twenty-one.

**So the finding is not "screen 03 is uncommitted". It is that the chip cannot
be trusted on this menu at all** — it is absent from three screens (05, 06, 07)
that genuinely have no specification, and present on one that has three. **A
step 2 lane must read §12's Screens column and ignore the chips.**

The screens with a genuine, measured absence of commitment in this lane are
**05, 06 and 07**, and for 06 and 07 that is a live oddity: screen 06 has five
of six steps rebuilt in §13 and screen 07 loses a step, and **neither change has
a specification row to carry it**.

---

## 6 · THE UI RULES, MEASURED

| rule | result |
|---|---|
| **40** — the page-head title is 32px on every screen | **PASS on all five, at both widths.** `getComputedStyle(h1).fontSize === "32px"`, weight 800 |
| **10** — required fields carry the asterisk on the label | **FAIL on screen 06** (F3). Pass elsewhere: `Full name*`, `Unit*`, `Service start date*`, `Move-in date*`, `Vacant unit*`, `Owner or developer*`, `Address*` all carry it |
| **7** — a date field is never a bare text input | **FAIL on `#dob`**, screens 03 and 04 — `input type=text`, placeholder `YYYY-MM-DD`. Already owned by `ACC-S4` / `R3`; not re-filed |
| **32** — a stated absence is a `<details>` CLOSED by default | **PASS** — every `<details>` found on all five screens reports `open: false` |
| **2** — one page header: kicker, title, actions | **PASS on all five** |
| **3** — a flow with 2+ stages uses the numbered rail | **PASS on all five** |

⚠ **RULE 33 IS BREACHED BY TWO WIZARD CAPTIONS AND IT IS NOT FILED, FOR A
REASON.** Screen 07's caption carries *"Everything below is a draft until you
press Create connection."* — ten words in one sentence, and rationale, which
rule 33 caps at **zero words on screen**. Screen 06's carries *"we need the name
and the address before this becomes a request with a number"* — fifteen. Both
are pre-existing strings; `G33` resolves **refusal** keys only, so neither is in
`g33_refusal_copy_baseline.txt` and neither is a new or changed string. B14's own
status column says rule 33 is *"NOT ENFORCED for these five kinds"*. **Recorded
here rather than filed, so a step 2 lane touching either caption knows it must
shorten it rather than carry it across.**

---

## 7 · WHAT THIS LANE COULD NOT CONFIRM, AND WHAT WOULD SETTLE IT

| open | what would settle it |
|---|---|
| screen 06's steps 2–6 as **rendered** | choosing a category and walking the six steps, once `DEF-CUS-5082` marks the field — or a fixture that pre-fills the draft |
| whether the seven rulings of F1 are complete | the blueprint's §13 was read end to end for these five screens; a ruling quoted only inside a drawing's dashed block could still be missed. The PDF landing in the repository closes this permanently |
| whether `?step=` on screen 06 is deliberate | `EP-SHL-03` says *all wizards*, and the capture page cites no exemption anywhere. Filed as a defect rather than a change on `13-change-process.md` §1's ambiguity rule |
| any commit-side behaviour | **nothing was submitted.** Step 1 writes no data, so every commit path here is read from code |

---

## 8 · WHAT IS DELIBERATELY NOT HERE

* **no open question was resolved by choosing a value** — the prime directive;
* **no deliberate refusal was filed as a defect** — §4 lists them instead;
* **no figure was quoted that was not measured** — §0 names the instrument for
  each;
* **no product code was changed.**

---

## Lifecycle

* packet: `CR-094-BRC01` §5 lane 3 · blueprint pinned at `033981d4f`
* generated: 2026-09-12 by the `CR-094-BRC01` step 1 lane 3 (claude)
* instruments: `10-scripts/cr094_lane3_starting_service_walkthrough.mjs` ·
  `10-scripts/cr094_lane3_walk_and_measure.mjs`
* rows filed: `DEF-CUS-5080` · `DEF-MET-5081` · `DEF-CUS-5082` ·
  `DEF-CUS-5083` · `DEF-CUS-5084` · `DEF-CUS-5085`
