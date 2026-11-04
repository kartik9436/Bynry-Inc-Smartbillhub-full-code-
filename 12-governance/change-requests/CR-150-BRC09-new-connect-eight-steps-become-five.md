# CR-150-BRC09 — New Connect: eight steps become five, one word each, and nineteen questions get answered

**Raised:** 2026-09-28, by the Product Owner, from the deployed build **`v2.385.1`** (Ottumwa Water
Works), one message at a time: *"i will tell you multiple bugs pleasw count it; we will process it
based on code at the end"*.
**Branch:** `claude/brave-dijkstra-xgfsgz` (`BRC09`). Block `CR-150`–`CR-154`, recorded in
`12-governance/14-id-reservations.md` **before this file was written**. Defect block
`DEF-CUS-7600`–`7629`, question block `OQ-CUS-12770`–`12779`, both in the same row.
`allocate.py cr --verify 150` at push time.
**Version:** `2.390.0` — allocated once for the whole change request. ⚠ **ONE LANE OWNS IT** (the
RECORD lane); the COMPONENTS and TEXT lanes were told not to bump, because two lanes bumping is
`DEF-GOV-3756`'s collision and `G35` holds four literals in lockstep.
**Classification:** ⚠ **MAINTENANCE, AND IT IS A MIXTURE OF DEFECT AND CHANGE — §1 says which part
is which.** A clerk can create a connection in the product today, so the PO's own test
(*can a user do this task in the product today?*) answers **yes** and this is the maintenance track,
not the build track.
**Screen-shaped:** yes. **Screen:** `NCT-01`, Accounts → New Connect, today at
`/{tenant}/connections/new`. **Screen owner:** ONE owner for the length of this change (§6).
**Drawing:** `05-prototype/new-connect-redesign-2026-09-28/` — **seven PNGs, and they are the
specification.**

---

## 0 · What arrived, in the requester's words

Nineteen questions were put to the Product Owner as they reviewed a redrawn New Connect; **eighteen
came back answered** and one is still open. Every answer is in
`12-governance/02-decision-log.md` under *2026-09-28 (late) · THE NEW CONNECT REDESIGN — THE
PRODUCT OWNER'S EIGHTEEN ANSWERS*, verbatim, so that no future session re-asks any of them
(hard-won law 13: *"this is very exzuating and taxing as a human… dont ask again and again"*).

**The one that reshapes the screen:**

> *"these steps are good - we need 1 word - for every step"*
>
> *"we dont want any information to be reduced or lost - 8 steps → 5"*

| New step | Carries | From today's steps |
|---|---|---|
| **1 · Customer** | the shared customer capture move-in already uses, gov-ID, date of birth, co-applicant, US mailing address, communication preferences, the Customer-ID search, the utility's own account fields, reference and mode, documents | 1, minus scope |
| **2 · Premise** | address search, the Scope dropdown under it, the record (parcel, route, lat, long, verified), one multi-select for services, the plan in full | 2, plus scope from 1 |
| **3 · Units** | one common selection with a required *Apply to all*, then one table — a row per unit and service, grouped by unit, with *Add row* and *Add work order* | 3, 4, 5 |
| **4 · Charges** | who is billed, payment terms, payment fields by payment type, billing preferences, the charges table with quantities | 6 |
| **5 · Review** | four collapsible groups each with *Edit*, the messages table with *Add template*, what pressing Create makes, Create connection | 7, 8 |

**Parked drafts and old links are part of the ruling, not a consequence of it:** a build parked on
an old step reopens on its mapped one — **1→1, 2→2, 3/4/5→3, 6→4, 7/8→5** — nothing a clerk already
typed is lost, and an old `?step=6` link goes to the new step.

**The other ruling that governs how this is built**, on the drawings:

> *"please ensure you usgae drawing images anot not text/content to create screensin b[product and
> use Ui skills, spcaing, font setc - this is improtnt"*

That is **B14 rule 42** (a screen is built from the drawing AS AN IMAGE; extracted text is an index,
never the specification) and **B14 rule 44** (our UI standard decides how it is built — spacing,
sizes, the type scale, the tokens, the component kit — every time, on every screen, including the
frame). `00-all-screens.html` in the same folder is the source the PNGs were rendered from and
carries, per screen, the sentences deleted under rule 33 and what each control does. **Read it for
those. Never for layout.**

---

## 1 · Classification — which part is a defect and which part is a change

**In the beta a report is a DEFECT by default** (PO 2026-09-10: *"CR is change in product, defect is
product does not do what is expected"*), and `13-change-process.md` §1 says the ambiguous case is a
defect too, because **filing our own miss as a "change" quietly converts our error into the
customer's new requirement.** So the two halves are separated deliberately:

| Part | What it is | Why |
|---|---|---|
| **The 14 reported bugs** | **DEFECTS.** `DEF-CUS-7600`–`7613`, filed 2026-09-28, one row each with the PO's own words and its `escape_reason` | Every one of them is the product not doing what was expected of it: text where rule 33 allows none, a customer capture that asks less than the door beside it, a required answer that cannot be answered yet, two columns that can never hold a value, three controls doing one job, a bulk action that is optional, a payer option disabled by a typed-in literal, and a payment the clerk cannot record |
| **Eight steps becoming five** | **CHANGE.** The wizard has eight steps because eight steps were agreed and drawn | Nothing was wrong with them. The PO has used the product and now wants a different shape: *"these steps are good - we need 1 word - for every step"*. That is the *yes* side of the PO's own test |
| **The 18 answers** | **Mixed, and each is stamped where it lands** — some settle a defect (11, 12, 4), some add capability nobody had asked for (latitude/longitude and a verified tick, communication and account preferences, a books entry at creation), and some simply confirm what the product already does (the plan is the premise plan; rows stay editable) | Recorded once, in the decision log, with the PO's words |

### ⚠ THE REDESIGN CASE IS NAMED IN THE MAINTENANCE PROCESS, AND THIS IS IT

`12-governance/22-product-maintenance-process.md` calls this shape out **by name**, on the PO's own
instruction, because the general rule will not survive contact with it:

> **A redesign of a screen people already use is MAINTENANCE**, and it **BORROWS EXACTLY ONE THING
> FROM BUILD: the drawing step.** It must have a drawn specification in the tree, agreed with the
> PO, before code — and it keeps every regression and reporter duty. **Nothing else crosses over.**

**Why that matters here and is not bookkeeping: it FEELS like building.** Seven new wireframes,
three lanes, hundreds of lines. A lane that follows the build track loses the four things this
process exists for — **no reproduce, no blast radius, no regression walk of the neighbouring
screens, and nobody tells the beta users their screen changed underneath them.** It has already
gone wrong once this month, on the property Overview, which shipped with three rows missing and
four labels different, every suite green.

**So this change is executed on the maintenance track**: reproduce (done — the PO reproduced all 14
on the deployed build and their words are in every row), locate, blast radius, the minimal fix per
finding, proof in a browser against the reproduction, a regression walk of the neighbours, version
and rollback, and a close that **tells the reporter which build to look in**. The drawing step is
the one thing borrowed, and it is already done: the seven PNGs are on the branch.

---

## 2 · What is being reversed — quoted, with the supersedes chain

| Signed statement, in its own words | What happens to it |
|---|---|
| **The Accounts blueprint's EIGHT DRAWN STEPS**, `05-prototype/02 Accounts Menu Blueprint.pdf`, which `B14` rule 41 makes exact (*the product UI matches the blueprint EXACTLY*) and `CLAUDE.md`'s blueprint ruling of 2026-09-14 gives layout, copy, **flows** and states | ⚠ **SUPERSEDED 2026-09-28 BY PO RULING, AND THIS IS THE ONE THING THAT CAN SUPERSEDE IT.** B14 rule 41's own text names the single exception: *the only thing that reaches the PO is a drawing that contradicts a signed rule*, and here the PO has ruled directly on the drawing. **A wizard's STEP COUNT is a flow**, which is exactly the word that cost the Billing wizard its shape — `DEF-GOV-5248`. The PO's words are recorded verbatim in §0 and in the decision log; **no lane may build eight steps because the blueprint draws eight.** |
| **The drawings of record become the seven PNGs**, not the blueprint and not r10 | `05-prototype/new-connect-redesign-2026-09-28/step1-customer.png` · `step2-premise.png` · `step3-units.png` · `step3a-add-row.png` · `step3b-add-work-order.png` · `step4-charges.png` · `step5-review.png`. **Built from AS IMAGES** (rule 42), with spacing, sizes, the type scale and the kit from `04-docs/02-decisions/14-ui-conventions.md` (rule 44). Every figure on them — *Jonas Janssen*, `$1,035.00`, `C-00010`, the Ottumwa address, every count — is an **ILLUSTRATION** (rule 37) taken from the PO's screenshots of `v2.385.1`. **Build the shape; never hard-code a figure off the drawing.** |
| `OQ-CUS-12391` — *when a build has a common area, does the one plan chosen at step 2 cover it, or does the common area take its own plan* — **OPEN since 2026-09-16** | ⚠ **CLOSED 2026-09-28, OPTION (a).** PO verbatim: *"simialr to unit - apply same plan that we have given to premises"*. The register row's **status and its body** both move, and the fan-out is walked in the same commit (§3). |
| `BR-MET-1178` (PO 2026-09-21): a build **prices itself**, the client sends `(charge_code, quantity)` and the QUANTITY IS COUNTED, never typed | **NOT REVERSED, AND DELIBERATELY NOT WIDENED.** Whether a quantity may be typed per charge is `OQ-CUS-12770`, **OPEN**. A Qty column is drawn on step 3 and may already be the answer; **nothing builds it until the question is ruled**, because it multiplies a price on a real invoice. |
| `BR-BIL-024` (PO 2026-08-23): **payment terms carry NO DEFAULT** | **UNCHANGED AND RESTATED HERE ON PURPOSE**, because step 4 now grows four payment fields around it and a lane adding *"30"* as a convenience would start a late-fee clock on a real invoice. |
| The PO's ruling of **2026-09-22** that a document's verification state reads *verified* or *rejected* and **no third word** | **UNCHANGED.** The two columns are HIDDEN on the wizard rather than filled with provisional values — PO 2026-09-28: *"keep today's behaviour and hide the two columns until creation"*. The DATA behaviour is ratified; only the presentation moves. |
| `apps/metering/connections.py::commit_connection` — a build whose quote **cannot be posted** commits anyway and records the figure alone (`connection.quote_total` set from the client, `one_time_charge_invoice_no` **`None`**, an `absence` appended and the commit continues) | ⚠ **SUPERSEDED 2026-09-28.** PO verbatim: *"we create entries in books"* and *"do it at creation once submitted"*, over this sentence shown to them: *"It is one act: if the books entry cannot be written, the connection is not created either."* **This is the largest piece of new work in the change and it is a money path.** |

**No ❄️ FROZEN B4/B5 figure is touched.** Nothing here changes rating math, a golden test or a
signed money figure; no finance re-sign is required, and none is being taken as read.

---

## 3 · Impact — the eleven surfaces

| Surface | What it comes to |
|---|---|
| **User stories** | The New Connect stories under `04-docs/05-modules/03-customers/06-epics` and `04-metering/06-epics`. **None becomes obsolete** — every field survives, so no story loses its subject; what changes is which step each case is performed on. Their test cases are amended, never deleted. |
| **Business rules** | **Amended in this change:** `04-docs/05-modules/03-customers/02-business-rules.md` (step 1's capture, the Customer-ID search, documents, communication and account preferences, the charges step's payer and payment) and `04-docs/05-modules/04-metering/02-business-rules.md` (the premise step, the unit rows, occupancy on the unit, the common-area plan, and the books entry at creation). **Re-read and unaffected:** `BR-MET-112` (nothing is written until the last button), `BR-MET-1178`, `BR-MET-1179`, `BR-BIL-024`. |
| **Build steps / waves** | No reordering of the product's build order. Inside the change, the record lands first (this file, the decision log, the rules, the defect rows), then the shared components, then the screens — because a screen built before its component is a screen that will be built twice (B14 rule 43). |
| **Documents** | This file · `12-governance/11-change-requests.md` (index row) · `12-governance/02-decision-log.md` · `12-governance/01-open-questions.md` (one closed, one minted) · `12-governance/14-id-reservations.md` · the two `02-business-rules.md` files · `CHANGELOG.md` · `12-governance/25-handover-2026-09-28-evening.md` §2, whose open-question table is answered by this change. |
| **Code** | `07-frontend/src/features/customers/NewConnect*.tsx` (every step), `07-frontend/src/components` (the shared table, the searchable select), `07-frontend/src/i18n/locales/*.json` (eleven catalogues), and on the backend `apps/metering/connections.py` for the books entry. ⚠ **ONE PART IS ON A MONEY PATH AND IS TREATED AS ONE** — the invoice and payment written at creation. It is **not** 🔒 by the sensitive-paths list (no RLS policy, no rating math, no ledger posting service, no rounding), but it posts a receivable, so it carries hard rule 2, hard rule 4, hard rule 7 and law 14's savepoint trap. |
| **Test cases** | The stories' cases are re-pointed at the five steps. ⚠ **TWO EXISTING ASSERTIONS BECOME FALSE AND ARE NAMED IN §4** rather than discovered later. |
| **E2E journeys** | Every journey and walkthrough that drives New Connect by step NUMBER — `10-scripts/po_new_connect_clerk_walk.mjs`, `10-scripts/cr094_new_request_six_steps_walkthrough.mjs`, `10-scripts/cr126_build_record_walk.mjs`, `10-scripts/cr126_s9_acceptance_walk.mjs`, `10-scripts/def_cus_5186_new_connect_step1_walkthrough.mjs`, `def_cus_5468_new_connect_step2_walkthrough.mjs`, `def_cus_5480_step4_grid_walkthrough.mjs`, `def_cus_5483_charges_walkthrough.mjs`, `lane_e_new_connect_split_capture.mjs`, `laneh_w2_step34_walkthrough.mjs`. **They will fail correctly.** A walk that asserts *step 6 of 8* is asserting a superseded truth. |
| **Seed data** | Unchanged. No seeded utility describes the step count. ⚠ **One fixture gap is worth adding rather than absorbing:** every seed builds contiguous units `1..n`, which is why `DEF-CUS-7605`'s From/To range satisfied every test — a non-contiguous set (units 1, 2 and 15, which is the PO's own screenshot) belongs in a fixture. |
| **Open questions** | **CLOSES `OQ-CUS-12391`** (the common-area plan), option (a). **MINTS `OQ-CUS-12770`** — *which quantities were 1, 2 and 15* — which is the only thing on this change nobody may answer. **RE-OPENS nothing.** ⚠ Checked in both directions by reading the register, not by grep, as this step's own instruction requires. |
| **The demo fixture** | A person driving the demo utility sees a five-step wizard that collects everything the eight collected. Coherent. |
| **THE DRAWING** | **`05-prototype/new-connect-redesign-2026-09-28/` — seven PNGs, named one by one in §2**, plus `00-all-screens.html` for the deleted sentences and the control notes. This surface **refuses** rather than asks (`13-change-process.md` §3, 2026-09-10), and the drawing exists before any code, which is the one thing this maintenance track borrows from the build track. |

### ⚠ The fan-out for `OQ-CUS-12391`, walked rather than assumed

Closing a question is a fan-out, not a status edit — one ruling on 2026-09-04 left eight surfaces
saying different things. Every surface that names this question was found with a repository-wide
grep and is accounted for here:

| Surface | State |
|---|---|
| `12-governance/01-open-questions.md` line 590 — the **status column** | **CLOSED 2026-09-28 — PO ruling, option (a)** |
| the same row's **BODY**, which is what a lane actually reads | **AMENDED in the same commit.** It described a world where nothing is chosen and listed three costed options; leaving it would tell the next lane to stub |
| `12-governance/02-decision-log.md` | The new dated entry records the ruling verbatim. The two 2026-09-16 mentions are the HISTORY of how the question arose and are left exactly as they are |
| `04-docs/05-modules/04-metering/02-business-rules.md` | Gains the rule, CONFIRMED 2026-09-28 — premises and units are metering's subject |
| epic · execution plan · story frontmatter | ⚠ **NONE NAMES IT** — verified by grep across the whole tree, not assumed. The only other mentions are `12-governance/10-defect-log.csv`'s `DEF-CUS-5496` row (history, unchanged) and the code Trace block below |
| `07-frontend/src/features/customers/NewConnectPlansStep.tsx:23` — `// Questions: OQ-CUS-12391 … OPEN; nothing here chooses a value for it.` | ⚠ **OWNED BY THE TEXT LANE, NOT THIS ONE, AND NAMED HERE SO IT IS NOT LOST.** It is the one surface the RECORD lane must not touch. **A Trace block citing a closed question as OPEN is a stale record that instructs the next lane to stub** — it moves in the TEXT lane's commit, `T-7` in §6 |

---

## 4 · What is already built and is now wrong

### Code already shipped on the old rule

| Where | What it does today | Why it is now wrong |
|---|---|---|
| `07-frontend/src/features/customers/NewConnectWizard.tsx` | eight steps, and refuses to advance past step 1 while `draft.scope` is empty | Five steps; scope moves to step 2 under the address search and becomes a dropdown pre-filled from what was found (`DEF-CUS-7602`) |
| `NewConnectOwnerStep.tsx` | sub-category, email, phone, prefix, external reference; `customerSearch` by NAME | Takes the shared capture move-in takes, and searches by **Customer ID** on the details entered above (`DEF-CUS-7601`) |
| `NewConnectOwnerStep.tsx` ~684, `draftDocumentRows()` | `uploaded_by_name: null`, `uploaded_at: null`, `document_number: null`, **and a comment still saying New Connect asks no document number** | The two columns are hidden until the connection exists; a **Document number** column (last four) is added for the box the form already has; the comment is stale and goes with the change (`DEF-CUS-7603`) |
| `NewConnectPremiseStep.tsx` — the services picker | service chips with an x, an *Add a service…* box and a second dropdown: three controls doing one job | One multi-select, no search, and the plan shown in full as label/value pairs (`DEF-CUS-7604`) |
| `NewConnectPremiseStep.tsx` — *Unit, apt. or suite*, and the record block | the unit box is **disabled**; the record has no latitude, longitude or verified tick | The unit box is **enabled and optional** (*"why have you disabled it if it is part of premise address then it should be there"*) and the record gains the three optional fields. ⚠ **NEITHER WAS REPORTED AS A BUG AND NEITHER IS FILED AS ONE** — they are answers 10 and 11, new capability rather than a miss, and `BR-MET-1184` carries them |
| ⚠ `NewConnectChargesStep.tsx` — the charge table's quantity | every line reads **qty 3** from the *What is counted* block (*"Counted from step 4."*) and **there is no editable quantity cell anywhere in the wizard** | The clerk entered **1, 2 and 15** earlier and the invoice does not reflect them (`DEF-CUS-7609`). ⛔ **AND NOTHING IS BUILT HERE UNTIL `OQ-CUS-12770` IS RULED** — they may be the unit LABELS, in which case the counted 3 is right, or per-charge quantities, in which case every line is wrong. It multiplies a price on a real invoice |
| `NewConnectUnitsStep.tsx` | a From/To range that generates rows | A table with *Add row* at the bottom — a range cannot express units **1, 2 and 15**, which is the PO's own screenshot (`DEF-CUS-7605`) |
| `NewConnectServicesStep.tsx` | a bespoke grid; *Copy unit 1 to all* optional; a plain work-order select | One shared table, grouped by unit, with a **required** *Apply to all* and rows that stay editable, and a searchable work-order select (`DEF-CUS-7606`, `7607`, `7608`) |
| `NewConnectChargesStep.tsx` ~651 and ~663 | `available={false}` **passed as a hardcoded literal** at both sites, under *"Those accounts do not exist."* and *"Nobody can settle this debt."* | All three payer options stay on screen — PO: *"this is wring - keep previous options"* — and a disabled one is disabled **by a real check** (`DEF-CUS-7610`) |
| `NewConnectChargesStep.tsx`, *Taking payment* | Payment terms and Posting date only, under *"No payment is taken here. Record it against the account."* | Payment option, amount, date and a reference whose label follows the option (`DEF-CUS-7611`). ⚠ **Payment terms keep NO DEFAULT** (`BR-BIL-024`) |
| `NewConnectCommsStep.tsx` | three hardcoded rows; a separate template search | The shared table with *Add template* below it (`DEF-CUS-7612`) |
| `NewConnectReviewStep.tsx` | four unlabelled ideas run together, occupancy asked here with four explanatory lines under it | Four collapsible groups each with *Edit*; **occupancy moves onto the unit rows on step 3** and the review step shows it without asking it (`DEF-CUS-7613`) |
| `NewConnectPlansStep.tsx` | exists as its own step (work orders) | Folded into step 3. Its Trace block also cites a question that is now closed — see §3 |
| ⚠ `06-backend/apps/metering/connections.py::_post_connection_quote` + `commit_connection` ~4474–4514 | When the quote **cannot** be posted the code takes `data["quote_total"]` from the client, saves it, sets **`one_time_charge_invoice_no` to `None`**, appends an `absence` — and **the commit continues**. Five codes reach that branch: `build_names_no_charge`, `quote_has_no_chargeable_line`, the payer's own code, `quote_payment_terms_not_captured`, `billing_quote_door_unpublished` | **The books entry and the payment are written in the SAME ACT as the connection, and if the books entry cannot be written the connection is not created.** ⚠ **A build that names no charge has nothing to write and is unaffected** — the rule bites where there IS an entry and it fails. This is the largest piece of new work in the change and the only part of it on a money path |

### Data already written

**Parked and in-flight drafts.** A `connections` row in `draft` carries the step a clerk stopped
on. **Nothing is migrated and nothing is rewritten:** the mapping `1→1, 2→2, 3/4/5→3, 6→4, 7/8→5`
is applied when the draft is REOPENED, and an old `?step=` link redirects. **No clerk loses a
keystroke**, which is the half of the PO's ruling that is easy to read past.

**Committed connections are untouched.** Nothing about this change rewrites a connection, an
invoice or a payment that already exists.

### Lanes building right now

**Three, all on `claude/brave-dijkstra-xgfsgz`, and none is stopped.** RECORD (this file and every
governance surface), COMPONENTS (new files under `07-frontend/src/components`) and TEXT
(`07-frontend/src/features/customers/NewConnect*.tsx` and the eleven catalogues). They are split
**by file**; the SCREEN has **one owner** per `13-change-process.md` §6. **In-flight work LANDS;
nothing is redirected.**

### ⚠ Which checks are now wrong — named by file, before any code is written

**A check left asserting a superseded truth is not neutral: it actively defends the old behaviour,
and the next lane reads its green as permission.** Checks that do not check are the LARGEST
category in this register.

| Check | What it asserts | What must happen |
|---|---|---|
| `06-backend/tests/test_w6_connections.py:1831` | `assert result["manifest"]["one_time_charge_invoice_no"] is None` — a build that commits **with no books entry** | ⚠ **THE WORST OF THEM, BECAUSE IT WILL GO ON PASSING.** Under the ruling a build with a chargeable quote that cannot be posted is **not created at all**. Re-point it: either the build names no charge (then `None` is right and the case should say so in its name), or the commit is refused. |
| `06-backend/tests/test_po20260921_a_build_prices_itself.py:303` | `assert not result["manifest"]["one_time_charge_invoice_no"]` beside `build_names_no_charge` | **Still correct, for the case it actually covers** — a build naming no charge has nothing to write. Amend its REASON, not its figure, so the next reader does not widen it. |
| `07-frontend/src/features/customers/NewConnectWizard.test.tsx` | the eight-step order, the step labels and the scope gate on step 1 | **Amend to five.** It will fail loudly and correctly, which is the right kind of failure. |
| `10-scripts/po_new_connect_clerk_walk.mjs` · `cr094_new_request_six_steps_walkthrough.mjs` · `cr126_build_record_walk.mjs` · `cr126_s9_acceptance_walk.mjs` · `def_cus_5186_new_connect_step1_walkthrough.mjs` · `def_cus_5468_new_connect_step2_walkthrough.mjs` · `def_cus_5480_step4_grid_walkthrough.mjs` · `def_cus_5483_charges_walkthrough.mjs` · `lane_e_new_connect_split_capture.mjs` · `laneh_w2_step34_walkthrough.mjs` | drive the wizard by step NUMBER and assert *step N of 8* | **Re-pointed at the five.** A walkthrough naming a step that no longer exists fails for a reason that reads as unrelated — which is exactly the failure mode this row exists to pre-empt. |
| `06-backend/tests/test_br_met_040_common_area.py` | a common area's plan | **Grows the case the closed question leaves behind:** a common-area unit takes the **premise plan**, the same one every other unit gets. Today's `commitPlanOf` maps `unit.isCommonArea ? draft.planCommonArea : draft.planApartments` and `planCommonArea` is never set. |
| `G13` (a component's prop is passed) | that `available` is passed to the payer options | ⚠ **IT PASSES TODAY AND IT IS SATISFIED BY A LITERAL `false`.** G13 asks whether a prop is PASSED; **nothing asks whether a REFUSAL IS STILL TRUE.** It cannot be taught this one cheaply, so the fix is the rule CLAUDE.md already states — write the test that fires when the hold expires, in the same commit. |

### ⚠ One finding that is not a New Connect bug at all, and is filed rather than tidied

**`DEF-GOV-7614`** — six strings in the tree read `CR-140-BRC09` (`10-scripts/gates/run_gates.py:609`,
`10-scripts/gates/g133_export_columns_agree.py:4`, and three files under
`07-frontend/src/features/ledger/`), while `CR-140` is really **`CR-140-BRC07`**. Found while
claiming `BRC09` for this branch: a grep for the next free branch code returns six hits that are
somebody else's number with a mis-typed suffix. **Nothing is renumbered** — that is a mass
shared-file rewrite across five files this lane does not own, for a provenance string, which is the
thing law 11 exists to prevent. **The NUMBERS do not collide** (140 against 150–154), which is the
guarantee `G17` enforces. The defence taken instead is the cheap one: the fact is PRINTED beside the
claim, in the `BRC09` reservation row.

---

## 5 · Sized and confirmed — in plain English, with the figure

**What changes.** A clerk connecting a new property answers the same questions in **five screens
instead of eight**, each named in one word: Customer, Premise, Units, Charges, Review. Nothing they
used to be asked disappears. Three things they were never asked appear — where the bill is posted,
what the property's coordinates are, and how the customer wants to be contacted — and one thing
they had to do twice, recording a payment taken at the counter, is done once.

**What it costs.** Five screens rebuilt from seven drawings, two new shared components (a table
that grows and a searchable select) used by five tables between them, one backend change on a money
path, eleven locale catalogues, and roughly a dozen walkthroughs re-pointed from eight steps to
five.

**What breaks, and the figure that matters.** **Every walkthrough that drives this wizard by step
number** — ten of them, named in §4 — and two backend assertions that today prove a build can
commit **without** reaching the books. **For a clerk, one visible behaviour change beyond the
shape:** a build whose one-time charges cannot be written to the books **will no longer be
created**. Today it is created and the money is remembered as a figure on the build with no
invoice — **`one_time_charge_invoice_no` is `None`** — so nothing reaches Billing or Finance and
nobody is ever asked for it. On a build like the drawn example that is **`$1,035.00` that exists on
one screen and in no ledger.** After this change the clerk is stopped and told, which is a worse
moment and a better outcome.

**What nobody may guess.** `OQ-CUS-12770` — which quantities were 1, 2 and 15. Every charge line
reads `qty 3` from the unit count today; the PO entered 1, 2 and 15 somewhere earlier. They may be
the unit LABELS (step 4's own summary prints *Units 3 · 1, 2, 15*), or they may be per-charge
quantities. **It multiplies a price on a real invoice, so the Qty column is drawn and not built
until the PO rules.**

**How we will know it looks right.** Each of the five screens compared **row by row against its
PNG** — every label, in the drawn order, on the rendered page — walked at **1280 and 1440** by the
screen owner, with each string measured against B14 rule 33's five caps and the spacing and type
taken from the UI standard rather than from the drawing (rule 44).

---

## 6 · Execute — through the maintenance process, with the drawing step borrowed

Three lanes, each in its own `git worktree` from a pinned tip, each owning its own files. **The
screen has ONE owner** — splitting by file protects the code and fragments the design, which is the
`CR-089` lesson.

| Lane | Owns |
|---|---|
| **RECORD** | this file · `11-change-requests.md` · `02-decision-log.md` · `01-open-questions.md` · `14-id-reservations.md` · both `02-business-rules.md` · `10-defect-log.csv` · the version and `CHANGELOG.md` |
| **COMPONENTS** | new files under `07-frontend/src/components` — the table that grows, the searchable select |
| **TEXT** (the **screen owner**) | `07-frontend/src/features/customers/NewConnect*.tsx` and `07-frontend/src/i18n/locales/*.json` |

**Task status**

| # | Task | Owner | Status |
|---|---|---|---|
| R1 | Reserve the ids before anything is filed — `DEF-CUS-7600`–`7629`, `OQ-CUS-12770`–`12779`, `CR-150`–`154` as `BRC09` | RECORD | **DONE** `58d69beaf` |
| R2 | The 14 defect rows, each with the PO's words, the screen and its `escape_reason` | RECORD | **DONE** — `DEF-CUS-7600`–`7613` |
| R3 | This file + the index row in `11-change-requests.md` | RECORD | **DONE** |
| R4 | The 18 answers in the decision log, verbatim, so nobody re-asks | RECORD | **DONE** |
| R5 | `OQ-CUS-12391` closed — status AND body — and the fan-out walked (§3) | RECORD | **DONE** |
| R6 | `OQ-CUS-12770` minted — the quantities — and cited wherever the Qty column is built | RECORD | **DONE** |
| R7 | The rulings into `03-customers` and `04-metering` business rules, CONFIRMED or SUPERSEDED with the date | RECORD | **DONE** |
| R8 | Version `2.390.0` — the four `G35` literals + `CHANGELOG.md`, same commit | RECORD | **DONE** |
| C1 | The shared growing table (units, service points, work orders, charges, messages) — a COMPONENT, per rule 43 | COMPONENTS | owned by that lane |
| C2 | The searchable select (work orders, templates) | COMPONENTS | owned by that lane |
| T1 | Step 1 · Customer, from `step1-customer.png` AS AN IMAGE | TEXT | owned by that lane |
| T2 | Step 2 · Premise, from `step2-premise.png` | TEXT | owned by that lane |
| T3 | Step 3 · Units, from `step3-units.png`, `step3a-add-row.png`, `step3b-add-work-order.png` | TEXT | owned by that lane |
| T4 | Step 4 · Charges, from `step4-charges.png` | TEXT | owned by that lane |
| T5 | Step 5 · Review, from `step5-review.png` | TEXT | owned by that lane |
| T6 | Parked-draft mapping and the `?step=` redirect | TEXT | owned by that lane |
| T7 | ⚠ `NewConnectPlansStep.tsx`'s Trace block stops citing `OQ-CUS-12391` as OPEN | TEXT | **OWED** — named here because a Trace citing a closed question instructs the next lane to stub |
| B1 | The books entry and the payment written in the same act as the connection; a chargeable quote that cannot be posted refuses the commit | **MONEY** (taken 2026-09-28) | **DONE** — `apps/metering/connections.py` step 6 + `apps/metering/seams.py`'s four payments doors. The commit refuses on `metering.connection_books_entry_required` for every absence except the two that mean *nothing to write*; **the client's `quote_total` is written nowhere** (`DEF-MET-7641`) and may only REFUSE a bill that disagrees with the screen; the payment is recorded through `payments.services.record_payment`, allocated `specific` to the bill just raised, with the hand-tender till rule called at its one implementation. Idempotency: `payments.webhook_key` `UNIQUE (tenant_id, webhook_key)` (B2 DB-12) from `entry` + `new-connect:<connection id>`, behind the existing DRAFT-state guard. Manifest gains `one_time_charge_payment_no` and `one_time_charge_paid`. Proved RED first; the transaction and isolation cases run on **real PostgreSQL** (law 14) |
| B2 | The two backend assertions in §4 re-pointed | **MONEY** | **DONE** — neither deleted. `test_w6_connections.py`'s case is renamed to state it is the NO-CHARGE exemption `BR-MET-1187` names, and ⚠ **it had been RED since 2026-09-21 on a separate fault nobody had filed**: it asserted `no_quote_on_this_build`, a code `BR-MET-1178` replaced with `build_names_no_charge` seven days earlier. `test_po20260921_a_build_prices_itself.py:303` keeps its FIGURE and gains its amended REASON with a *do not widen* warning |
| B3 | The new cases — `06-backend/tests/test_br_met_1187_books_entry_at_creation.py` | **MONEY** | **DONE** — the invoice with its lines on the owner's account · the due date as posting date + typed terms · absent terms refuse · a failed books entry leaves no unit, no invoice and no payment · the no-charge exemption commits and records no figure · a total the bill disagrees with refuses · the payment recorded against that invoice · no payment recorded when none was taken · an amount with no tender refused · a tender with no amount refused · zero refused · cash with no till refused (card beside it as the control) · **two presses, one invoice and one payment** · the idempotency key asserted as a string and its replay · an audit delta per money action · tenant isolation |
| W1 | The ten walkthroughs re-pointed from eight steps to five | with TEXT | **OPEN** |

---

## 7 · Version

**`2.390.0`** — the middle number, because a restructure of a wizard is a change rather than a fix.
One allocation for the whole change request, taken with `10-scripts/allocate.py version --bump
change` (which asks the REMOTE, not this checkout — three families collided in one afternoon on
2026-09-04 with every lane's arithmetic correct), landed in the four literals `G35` holds in
lockstep — `07-frontend/package.json`, `07-frontend/package-lock.json` **×2** and
`06-backend/pyproject.toml` — **with its `CHANGELOG.md` entry in the same commit**, because rule 4
of step 7 refuses a bump without one and `2.52.0` was cut with no entry the very next version after
that rule was written.

⚠ **`package-lock.json`'s two fields are edited IN PLACE and `npm install` is NOT run**, which
would move dependency resolutions under two live lanes and turn a four-line change into an
unreviewable diff.

---

## 8 · Close — and the rollback, stated before shipping

### ⛔ This CR is NOT closed

Per the closure bar (PO ruling 2026-08-18): *"in this session CR is not closed until we have confirm
user is able to perform tasks using screen/broswer/UI"* — **and its fourth row, added 2026-09-09:
the screen compared to its DRAWING, row by row.** Nobody has yet opened the five-step wizard and
created a connection. What exists at this commit is **the record**: the change request, the
eighteen answers, the fourteen defect rows, the closed question, the new question, the amended
rules and the version.

**What is owed before it can close**, named rather than implied:

* the five screens built from their PNGs and walked at 1280 and 1440, row by row against the
  drawing;
* ~~the books entry written in the same act as the connection~~ — **task `B1`, DONE 2026-09-28 by
  lane MONEY** (`BR-MET-1187`, `DEF-MET-7641`). ⚠ **It is built and it has not been CLICKED**: the
  closure bar is a person creating a connection through the screen, and step 4's payment fields are
  the TEXT lane's (`DEF-CUS-7611`). The backend contract those fields must post is
  `payment_method` (a tenant method CODE, not a drawn label — *Cheque* is `check`, *Bank transfer*
  is `ach` or `wire`), `payment_amount`, `payment_date`, **`payment_cleared_date`**,
  `payment_reference`, `payment_memo`, all optional, and *No payment now* is simply sending none.
  ⚠ **THE CLEARING DATE IS A FIELD THE DRAWING DOES NOT HAVE AND THE MONEY NEEDS**: without it the
  payment is `processing` under `BR-PAY-021` — it meets no bill and posts no ledger pair — which is
  right, and silent unless the screen asks. Shipped as `2.391.0`;
* the ten walkthroughs re-pointed;
* `OQ-CUS-12770` ruled before any Qty column is built;
* **the reporter told which build to look in.** *"Fixed in 2.390.x"* is the whole requirement, and a
  beta tester who reports fourteen things and hears nothing stops reporting — at which point the
  beta produces no signal at all.

### The rollback

**The rule is the PO's and it is deliberately simple** (2026-09-10): *"for time being - Code only —
Revert the commit. Done."* What that costs here, honestly, per part:

| If this was wrong | What undoing it costs |
|---|---|
| The five-step shape, the components, the screens, the catalogues | **Reversible.** Revert the commits; the eight steps come back. No schema, no data. |
| The parked-draft mapping | **Reversible.** It is applied on reopen and writes nothing, so reverting it puts a draft back on the step it was parked on. |
| The record — this file, the decision log, the rules, the defect rows | **Reversible as text and pointless to revert.** A ruling that was made stays made; reverting the record only makes it unfindable. |
| ⚠ **The books entry at creation** | **NOT REVERSIBLE FOR ANY CONNECTION MADE WHILE IT WAS LIVE.** Reverting the code stops new invoices being raised; **the invoices and payments already written stay written**, and a payment is under hard rule 4 — no UPDATE, no DELETE, corrections are new rows. This is the maintenance process's own flag: *a fix that repairs data leaves the repaired rows behind when the code is reverted.* **It is a decision, not an experiment**, and it is stated here before shipping because that is what this step is for. |
| ⚠ **A build refused because its books entry could not be written** | **Not a data change and not undoable by a revert either** — the connection simply was never created, and the clerk re-enters it. That is the intended outcome and it is named so nobody reads the refusal as a fault. |
