# CR-089 — Premises & Units, rejourneyed

**Arrived:** 2026-09-08, in the working chat session, over roughly four hours of
the Product Owner walking the screens.
**Requester:** Product Owner.
**Classification:** a scope statement, twelve rulings, two reversals of our own
drafts, one reversal of live server behaviour, and 55 specifications minted from
stated absences.
**Status:** OPEN. Nothing built.
**Blueprint:** the analysis this CR executes is *Premises & Units Blueprint*
(23 screens, 55 specifications, 81 resolved absences, six-table appendix).

---

## 0 · CAPTURE — the requester's words, verbatim

The PO did not write a specification. They walked the product and said what was
wrong, in one or two sentences at a time, over four rounds. **The burden of
structuring is ours**, so their sentences are kept exactly as spoken and the
structure is added around them.

**The scope, set at the start:**

> *"Scope: what goes in the document - we dont need import in this - import is
> sorted; so 5 and 6 will not be required; but you will need create/edit/view -
> Presmise and Unit + list view for both and details view for both; We need to
> add GIS parameters on Premises and Units, We need to ensure we align the
> address field correctly - I dont want existing screen - based on existing
> screen if you can directly show me revised screeens we can work from there"*

> *"We will need parcel ID and we will ahve to display them - we will ahve to
> display GIS data on screen … you are correct address is on premsies/property -
> but GIS data for unit might change and hence we have to have parcel ID and GIs
> details on Unit also"*

> *"what impact you will ahve on Map because of this - you should take those
> changes also in this analysis . you will ahve changes when Premises, Units,
> Assets, Accounts, Bills, Payments are search by address - you should take those
> changs also into account."*

> *"you also need to check whether youa re able to link property owner and
> property later - master accoutns should eb conencted to property - that entire
> fucntionalities"*

**The standing constraint on how, said once and binding on all of it:**

> *"Also when you design the screens, ensure you follo the UI style guide, you
> optimise for information architecture, interaction design, User experience on
> that screen - **we are not going to change the existing rpocess or screens, we
> are going to optimize them for journies**"*

**On units and their assets:**

> *"on units, we will need capabilties to add Assets from Investory - search and
> assign functionalities will be required. ALso allow user to change status of
> assets atatched to unit - during the edit process - you can run this journey
> and figure out what are the problems"*

> *"Allow user to cahnge Unit and Premsies status"*

**Then, screen by screen, over three more rounds:**

> *"Services available = Utility services = drop down - multi select."* ·
> *"Owner = search ( it should be optional) - what if this owner has other
> properties in system - we shoudl give message"* ·
> *"you did nt allow to add any Common areas when we were creating premises"* ·
> *"We will need GIS verfieid Flag or field … at the time of creating and in view
> also"* ·
> *"Sub-area - field apper only in edit , it should be ther ein create , view as
> well"* ·
> *"In header we are not shouding Route and Cycle information - if it is assign or
> if it nor assign both the thing and you should add that at the time of creation
> also - it should be optional"* ·
> *"you need show pages for each tab within property page"* ·
> *"we dont need this right now - Drag the pin to correct it"* ·
> *"please improve the layout of this screen, interactive design, user
> experience"* ·
> *"05 Edit a property PRM-02 and create property screen should match - please
> update - it will help user to have simialr experience"* ·
> *"you ahve to show P-00080 also in header"* ·
> *"When we are creating Units - we are not using Numbering we have from settings
> - we ssign the unique number that is not coming out in units"* ·
> *"P5 Property → Units -> in table Unit IDs are not shown"* ·
> *"U1 The units list … whya re we showing these - Overview / Meters / Plan /
> Account / Occupancy / Audit log"* ·
> *"these should be 2 input fileds - Area · sub-area - not 1"* ·
> *"P7 Property → Meters - this should be assets - it will ahve all meter, sub
> meters, cart, ERu, fire - all kind of assets will be tagged here"* ·
> *"firs form should start with Search premises - there is no premsies and on
> search you should show premises details - summary"* ·
> *"youa re not allowing to add plan here from drop down - we shuld attached plans
> and it should be options, when I edit it later you should allow to change the
> plan ot apply the plan"* ·
> *"this should be wizard and you should show preview and create"* ·
> *"Unit → Overview - you are not showing unit ID here"* ·
> *"Unit → Overview -> Meter = assets"* ·
> *"Youa re not showing Unit move - screen"* ·
> *"Unit → Account - can you please check - what all other infrmation we can
> display about accounts here - and expand the details"* ·
> *"Kpis you ahve shown on Unit view - these KPis will be displayed across all
> views"* ·
> *"Unit → Overview - please display account if occupied"*

**And the sentence that authorises the build:**

> *"these are confirm - please build"*

---

## 1 · CLASSIFY — and the split is deliberately harsh on us

| What | Kind | Where it lives |
|---|---|---|
| GIS on premises and units, parcel numbers, the map and address-search reach, owner ↔ master account | **New requirement** | this CR, waves A and K |
| Status control on a property and on a unit; an edit screen for a unit; a review step for adding units | **New requirement** | this CR, waves D, E, F |
| 55 specifications minted from stated absences | **New requirement** | this CR, §6 |
| The owner stops being required at create | **Reversal of live server behaviour** | this CR, §2 |
| A unit may carry its own coordinates | **Narrowing of a signed rule** | `BR-MET-1162`, already ruled and recorded |
| One date written four ways on the plan screen | **DEFECT** | `DEF-MET-4689`, filed 2026-09-08 |
| Fire service line missing from three of ten tenants | **DEFECT** | `DEF-AST-4690`, filed 2026-09-08 |
| An account protection invisible from a unit | **DEFECT** | `DEF-CUS-4691`, filed 2026-09-08 |
| Nine account columns populated on zero rows | **DEFECT** | `DEF-CUS-4692`, filed 2026-09-08 |
| One sentence printed seven times; our implementation explained to a clerk | **DEFECT** | `DEF-MET-4693`, filed 2026-09-08 |
| A date format asked for in words; a machine's plural in a consequence | **DEFECT** | `DEF-MET-4694`, filed 2026-09-08 |
| The Assets tab drawn as *Meters*; area and sub-area drawn as one control | **DEFECT IN OUR DOCUMENT, NOT THE PRODUCT** | corrected in the blueprint; recorded in the decision log, fourth round |

⚠ **THE LAST ROW IS THE ONE WORTH READING TWICE.** Two of the changes we proposed
would have made the product **worse**, and in both cases the shipped code was
already right: `BR-MET-045` names the tab *Assets* and the component's tab id is
literally `"assets"`; the two-control area picker was ruled by this same PO on
**2026-08-17** and implemented as `BR-MET-071`. Filing our misunderstanding as a
"change" would have converted our error into the customer's new requirement,
which is exactly what step 1 of the change process exists to prevent. **Before
proposing that a screen change, read the component.**

---

## 2 · WHAT IS BEING REVERSED — quoted, never summarised

### 2.1 · One reversal of LIVE SERVER BEHAVIOUR

| Reversed | It used to do | It now does | Ruled |
|---|---|---|---|
| `metering.premises.owner_required` | refuse a create with no owner | accept it; the property lands on a *Needs an owner* list | *"Owner = search ( it should be optional)"* |

**The supersedes chain, in full.** The requirement was **create-only** and
deliberately not on PATCH, so that a ten-year-old address stayed saveable. That
reasoning still holds for PATCH and is untouched. What changes is the create
path, and the cost is named: a property can now exist with no party attached to
it, so **`PUJ-11` and the *Needs an owner* list are not optional extras — they
are what stops the reversal creating orphans nobody can find.**

### 2.2 · One narrowing of a SIGNED RULE, already ruled and recorded

| Rule | Before | After |
|---|---|---|
| `BR-MET-1161` — one home for an address | address, latitude, longitude and parcel all live on the premises; everything else walks to it | **the address half stands untouched.** The coordinate half is narrowed by `BR-MET-1162`: a unit may carry its own parcel and its own point, and where it does, those are the truth for that unit |

**Why the narrowing is safe, stated rather than assumed:** a map and an envelope
still cannot disagree, because the *address* has not moved. What has moved is a
point on a map, for the case the rule was never written for — a cabin, a pad, a
wing of a campus, where the site office is somewhere the unit is not.

⚠ **`g85_one_address_home.py` WILL GO RED, AND THAT IS THE GUARD WORKING.** It
counts latitude and longitude as address fields and fails a fourth home. Its
allow-list moves under `PUJ-54`, **with the ruling quoted in the line above the
two new entries**, so the next person to read it meets the reason rather than a
quietly loosened check.

### 2.3 · One rename of a live field

| Reversed | It used to say | It now says | Ruled |
|---|---|---|---|
| `premises.external_ref` label | *External / GIS ref* | **Parcel ID** | `BR-MET-1163` |

Costs nothing: the column is **empty on all 673 properties**, so no data is
overwritten and no migration is needed. Only the label and the help text move.

### 2.4 · Two proposals of OURS, withdrawn

Neither reverses signed law; both reverse a draft of the blueprint, and both are
recorded so the next reader does not re-propose them.

| Withdrawn | Why it was wrong |
|---|---|
| Renaming the Assets tab to *Meters* | the tenant's catalogue holds **thirteen asset types in three families** and only three are meters. The rename would have hidden ten — fire lines, carts, comms endpoints, backflow preventers, PV, batteries, EV chargers, generators, transformers, modems |
| Drawing area and sub-area as one control | the product already builds two, over one stored column, on a ruling from 2026-08-17 |

---

## 3 · IMPACT — the ten surfaces

| Surface | What moves |
|---|---|
| **User stories** | `US-MET-001` (premises detail) gains the location rows and the status control. `US-MET-003` (guided add) gains coordinates, parcel, GIS flag, common areas, route and cycle. **A new story is needed for editing a unit and for taking either thing out of service — none exists today**, which is hard-won law 8 (every screen needs a story). |
| **Business rules** | `BR-MET-1161` **amended, not superseded** — its coordinate clause only. `BR-MET-1162/1163/1164` are new and already recorded. `BR-MET-045` (the five-tab premises detail) is **re-cited and unchanged** — this CR does not add a tab. `BR-MET-007` (a unit's default plan) is **unchanged and finally rendered**: it has been signed all along and the wizard simply never drew the panel. `BR-MET-071` (two area controls, one column) unchanged. |
| **Build steps / waves** | Order unchanged in the product's build order: Premises/Units still sits after Plans & Rates and before Assets and Accounts. Inside this CR the order is fixed by dependency, not by preference — location before the screens that show it, creation before the tabs, the unit's page before its account tab. |
| **Documents** | `A1` screen inventory (S14, S15, S16 and the PRM-0x readouts), `04-docs/05-modules/04-metering/` (overview, business rules, field map, flows, user stories), and `05-prototype/r10` divergence stamps for the two screens that gain a status control. Every one in the same commit as its code. |
| **Code** | `06-backend/apps/metering` (models, services, selectors, api), `07-frontend/src/features/metering`, plus **read-only reach** into `apps/customers` for the account tab and `apps/assets` for the inventory picker. 🔒 **No rating-math file is touched.** No pricing path changes; `PUJ-35` renders a figure the engine already produces and computes nothing. |
| **Test cases** | `PremisesPage.test.tsx`, `AddPremisesWizard.test.tsx`, `AreaTagging.test.tsx`, `UnitsListPage` and the unit-detail tab tests. Every tab-strip assertion on the property and unit pages changes, because the four KPI tiles move onto every tab. |
| **E2E journeys** | Any journey asserting a two-step add-units flow will fail **correctly** — it becomes three steps with a review. The recording journey (`5 screens, 12 clicks, refused at the last one`) is the acceptance test for waves A and B and should be written before either lands. |
| **Locale catalogues** | All eleven. New keys for the location rows, the GIS-checked flag, the *Needs an owner* chip, the status-change refusals, the review-step labels, the asset group headings, the account tab's fifteen new rows, and the move screen's seven consequences. **Rule 35 applies: each catalogue is written in its own language, not translated from English.** |
| **Open questions — both ways** | **ANSWERS** nothing outright. **RAISES:** whether a unit that is *inactive* and *occupied* is billable — two pills sit side by side on every unit header today and no rule says what the pair means (Appendix F). **RAISES:** whether the units list's 1,109 includes common areas; nobody has said. **UNTOUCHED and still open:** whether the worked example month can ever be shown, which is a rating question and not this CR's. |
| **The demo fixture** | ⚠ **The fixture must be re-seeded or three waves cannot be demonstrated at all.** 16 of 673 properties have no coordinates and `gis_unchecked` is set on **none** of them, so `PUJ-01`'s filter would show an empty list and `PUJ-04`'s flag would have no true case. **Nine account columns are populated on zero rows across both demo utilities** (`DEF-CUS-4692`), so `PUJ-38` and `PUJ-41` have nothing to render. And **three of ten tenants have no `fire_line` type** (`DEF-AST-4690`), so a fire line cannot be tagged on `brazosbend` to prove `PUJ-15`. |

---

## 4 · WHAT IS ALREADY BUILT AND IS NOW WRONG

**Code shipped that this CR changes.** Nothing shipped is *wrong* in the sense of
producing a bad number — this is a journey CR, not a money CR. Four things
shipped correct and are now incomplete:

* the create endpoint **already accepts a nested plan block** and the wizard never
  drew the panel (`PUJ-25` renders what is already contracted);
* `premises.lat`, `premises.lng` and `gis_unchecked` **already exist** and are
  read by no screen (`PUJ-04`, `PUJ-10`);
* `account_protections`, `account_notes`, `account_collection_state` and
  `account_budget_status` **already hold rows** and no unit-side selector reads
  them (`PUJ-36`, `PUJ-39`, `PUJ-40`);
* the assets registry **already serves all thirteen types** and the property tab
  draws them undifferentiated (`PUJ-14`).

**Data already written that must be reconciled.** None is invalidated. Three
sets need attention before the screens can be believed:

| Data | Today | What this CR needs |
|---|---|---|
| 673 properties | 657 have a point, 16 do not, `gis_unchecked` false on all | the flag has to mean something; a backfill decision is **not** taken here |
| 1,109 units | none carries a point or a parcel | correct, and stays correct — a unit's point is opt-in by design |
| `premises.external_ref` | empty on all 673 | relabelled, not populated. **Backfilling parcel numbers is out of scope** — inventing them is not available to us |

**Lanes building right now, which the requester must be asked to stop or let
land.** ⚠ **One lane is live in the shared tree with 34 modified files**, on
services and units-of-measure. It touches `apps/metering/sample_data.py`,
`apps/metering/register_units.py`, `core/sample_fixture.py`,
`features/tenancy/SignupWizard.tsx` and all eleven locale catalogues. **Wave A
must not start in the shared tree until that lane lands**, because the fixture
re-seed above and their sample-data edits are the same files. Every wave of this
CR is dispatched into its own `git worktree` for the same reason.

---

## 5 · SIZE IT, IN PLAIN ENGLISH WITH A FIGURE

**This is a big change and most of it is small pieces.** Fifty-five separate
things, across eleven waves, on twenty-three screens. Counted from the
blueprint's own sizing table: **eleven small and twelve medium, none large.**

**Nothing here is a new rule or a new shape of money.** The only new columns in
the whole CR are two on a unit — its latitude and its longitude — and one flag
already exists.

⚠ **AMENDED 2026-09-08 BY WAVE A: IT IS FOUR COLUMNS, NOT TWO.** The two on a
unit are exactly as sized. What this paragraph did not foresee is where the
GIS flag's *"with who and when"* would live — `premises.gis_checked_by` and
`premises.gis_checked_at` (`metering/0055`). The alternative was reading
`audit_log`, and it was rejected because that table **is pruned on a retention
schedule** (CLAUDE.md hard rule 4; whether any row is exempt is `OQ-1340`,
OPEN): a screen naming a person out of it would print *Checked · D. Whitfield,
8 Sep 2026* today and *Checked · —* after the sweep, with nothing saying a fact
had decayed. The reasoning is in the decision log of 2026-09-08. Everything else is a screen showing something the database
already holds and no page reads.

**What it buys, with the figure that matters:** recording a building today takes
**five screens and twelve clicks**, and the first attempt was refused at the last
one, for an owner the form never marked as required. After waves A and B it is
**three screens**, the owner is optional, and a refusal lands on the field that
caused it.

**What it costs that is not obvious:** the four KPI tiles now render on every tab
of every property and every unit — six tabs each. That is four extra figures per
tab change. **At the top of the customer band that is the one ruling in this CR
whose cost grows with tenant size**, and it is named here rather than discovered
at 40,000 accounts.

**The fast path does not apply.** This touches rules, data and eleven locale
catalogues.

---

## 6 · THE TASKS

### ⚠ THE DRAWING FOR EVERY SCREEN IS IN THE TREE — ADDED 2026-09-09, AND IT IS WHAT A LANE MUST BUILD TO

**The source, named by the Product Owner:**

> **https://claude.ai/code/artifact/0d988b7d-aebf-476c-846b-bb635200f336**
> *Premises & Units Blueprint* — 23 screens.

**Extracted into `04-docs/05-modules/04-metering/09-screen-conformance.md`** —
header, actions in order, tabs, tiles with their detail lines, ordered fact rows
with their exact labels, table columns, footer, and the rules each screen obeys.
Verified against the live page: **23 drawn frames, 23 identical, 0 differing.**

⚠ **THE TASK ROWS BELOW ARE BEHAVIOUR SENTENCES AND THEY ARE NOT THE DESIGN.**
Every *done when* says what a person can DO. **None of them says what the screen
LOOKS LIKE** — and on 2026-09-09 the PO opened the property Overview and found
three rows missing, four labels different, one column drawn as two and the wrong
four tiles, with every task row satisfied. **A lane building only from the rows
below will reproduce that.** Build to the conformance file; the rows are the
behaviour it must also have.

This is the change process's eleventh impact surface, added the same day, and
its rule is: **name the file, not a page.**

### SCREEN CONFORMANCE — ONE OWNER PER SCREEN, AND WHAT IS STILL UNCHECKED

The process now assigns lanes **by screen, not by file** (§6 of the change
process, 2026-09-09). Every lane of this CR did its job correctly and the
property Overview still came out wrong, because five waves each added one row
and no lane owned the screen.

⚠ **EVERY SCREEN'S CONFORMANCE READS UNCHECKED, AND THAT IS NOT PESSIMISM — IT
IS THE HONEST STATE.** *Landed* means the wave's behaviour tasks are done and
walked. **It does not mean anyone has compared the screen to its drawing.** Only
P4 has been compared, by the PO, and it failed. The other 22 are unexamined.

| Screen | Name | Built by | Behaviour | Matches its drawing? |
|---|---|---|---|---|
| **P1** | The property list | A · B | LANDED | **UNCHECKED** |
| **P2** | Add a property · Details | B | LANDED | **UNCHECKED** |
| **P3** | Add a property · Review & save | B | LANDED | **UNCHECKED** |
| **P4** | Property → Overview | **OVERVIEW LANE** | IN FLIGHT — the PO found it wrong on 2026-09-09 | **UNCHECKED** |
| **P5** | Property → Units | C | LANDED | **UNCHECKED** |
| **P6** | Property → Common areas | C | LANDED | **UNCHECKED** |
| **P7** | Property → Assets | C | LANDED | **UNCHECKED** |
| **P8** | Property → Work orders | C | LANDED — **never walked**, no work order exists on any sample property | **UNCHECKED** |
| **P9** | Property → Audit log | C | LANDED | **UNCHECKED** |
| **P10** | Edit a property | B | LANDED | **UNCHECKED** |
| **P11** | Take a property out of service | D | LANDED | **UNCHECKED** |
| **U1** | The units list | E | LANDED | **UNCHECKED** |
| **U2** | Add units · Details | E | LANDED | **UNCHECKED** |
| **U3** | Add units · Review & create | E | LANDED | **UNCHECKED** |
| **U4** | Unit → Overview | F | LANDED | **UNCHECKED** |
| **U5** | Unit → Assets | G | IN FLIGHT | **UNCHECKED** |
| **U6** | Unit → Plan | H | LANDED | **UNCHECKED** |
| **U7** | Unit → Account | I | LANDED | **UNCHECKED** |
| **U8** | Unit → Occupancy | F | LANDED | **UNCHECKED** |
| **U9** | Unit → Audit log | F | LANDED — verified already correct, not rebuilt | **UNCHECKED** |
| **U10** | Edit a unit | F | LANDED | **UNCHECKED** |
| **U11** | Move a unit to another property | J | LANDED | **UNCHECKED** |
| **U12** | Take a unit out of service | D | LANDED | **UNCHECKED** |

**Closing this CR now requires the fourth row of the closure bar** — the screen
compared to its drawing, row by row, every label in the drawn order on the
rendered page. Until a screen has that, its conformance is an unchecked claim
and this table says so.


### ⚠ CORRECTION, 2026-09-09 — THE WORKED FIGURES BELOW ARE ILLUSTRATIVE, AND SOME NAME DATA THAT DOES NOT EXIST TOGETHER

**Read this before you treat a *done when* sentence as a test fixture.** Wave K
found it by trying to run one, and I then checked it against every tenant:

| What the sentences use | What is actually true |
|---|---|
| `412 Cypress Row` | Real, on **`brazosbend` only** — property `P-00080`, one unit, and **no accounts, no bills and no payments against it** |
| `A-10517` | **Exists on no tenant at all.** Zero rows, everywhere |
| `BL-2608-000052` | Exists on **eight tenants**, so the number alone identifies no bill; on `brazosbend` it stands at **101 Silver Creek Rd**, not at Cypress Row |
| `U-01144`–`U-01147`, `M. Alvarez`, `Creekside Holdings LP` | Illustrations carried over from the walkthrough, never looked up |

**How this got in, because the shape matters more than the fix.** These sentences
were written from the Premises & Units blueprint, whose figures are real readings
taken from **three different demo utilities** without saying which. The
blueprint's own Appendix F names that as its most expensive unstated assumption
and puts it last on purpose — *"a reader adding two of them together gets a
number that describes nobody"* — and this CR was then written from the blueprint
without re-checking the data against a single tenant. **The warning was correct
and it was not heeded by its own author.**

**What a lane should do about it.** Every *done when* below is a statement about
**what a person can do and see**, and that half is sound: the address, the
account number and the bill reference in it are examples, not fixtures. Honour
the shape of the sentence **at an address that carries the data**, say in your
report which address you used, and — as wave K did — walk the empty case too,
because *"returns nothing, correctly"* is also a claim.

**This changes no scope, no task and no ruling.** It changes which row you point
a browser at.


Eleven waves. **The status column is here from the day this CR is written**, and
every row starts `NOT STARTED`. A row moves to `DONE` only when a person has done
the thing on the screen — the closure bar, not a green test.

### Wave A · Where a property is · 9 tasks

| # | Task | Done when | Status |
|---|---|---|---|
| **A1** | `units` gains `lat` and `lng`, nullable, with a migration; `g85`'s allow-list moves with the ruling quoted above it (`PUJ-54`) | the guard passes, and the two new entries carry the 2026-09-08 ruling in the line above them | **DONE** — `metering/0055`. `G85` was proved RED first through `run_gates`' own entry point, then green; its entry is **field-scoped** (`HOME_FIELDS`), so a unit is a home for `lat`/`lng` and a `city` on one still fails BY NAME. Third self-sabotage added |
| **A2** | `premises.external_ref` is relabelled **Parcel ID** on create, edit and the property's page (`PUJ-20`) | the field reads *Parcel ID* in all three places and holds `R-114-0082-004` | **DONE** — all eleven catalogues. ⚠ The create form had **no such field at all**: it was in the payload and drawn nowhere. Walked: `P-00010` holds `R-114-0010-010` |
| **A3** | The property's page shows its point, its parcel and its GIS-checked flag (`PUJ-10`) | the Overview reads *Parcel R-114-0082-004*, *On the map 30.752104, −98.238391* and *Checked against GIS · Checked · D. Whitfield, 8 Sep 2026* | **DONE** — walked: *Parcel ID R-114-0010-010* · *On the map 30.266350, -97.742150* · *Checked against GIS · Checked · Dana Whitfield, 09/08/2026*. ⚠ The date is the TENANT's format through the shared formatter, not `8 Sep 2026`: the named-month rule is screen-wide and is `DEF-MET-4689`/wave H's, and a fifth formatter here would be that defect |
| **A4** | Coordinates, parcel and the GIS flag are captured at creation (`PUJ-04`) | after the lookup answers, the create form shows both, with *Not checked yet* and a **Mark checked** control | **DONE** — walked: *Parcel ID · Latitude · Longitude · Mark checked · Not checked yet* all on the form. Marking it checked records WHO and WHEN (two new columns; the reasoning is in the decision log) |
| **A5** | The address lookup reports its own failure (`PUJ-03`) | with the mapping service disconnected, a grey line reads *Address lookup unavailable — type the town, state and ZIP* instead of nothing | **DONE** — and the browser found the first draft was a check that could never fire: it read `error.body.error.message_key`, a shape this client never produces. It reads `ApiError.messageKey` now |
| **A6** | A point can be corrected on the edit form (`PUJ-19`) | a property placed on the wrong side of the street is corrected and the pin moves | **DONE** — the server refused `lat`/`lng` on a PATCH by name until this wave, so a wrong pin was permanent. A clerk is now the one writer allowed to overwrite a set value; the seed and the geocoder still are not. A coordinate outside ±90/±180 is refused at the field |
| **A7** | A unit may carry its own point and parcel, falling back to its building (`PUJ-27`) | a cabin reads *this unit's own point*; a flat reads *from the building* with **Give this unit its own point** beside it | **DONE for the POINT; the PARCEL is NOT built and is owed.** `units.external_ref` is `BR-MET-404`'s legacy match key under a unique index, and two units in one building share one parcel — it would refuse the second. Recorded on `BR-MET-1162` |
| **A8** | The property list can find the incomplete ones (`PUJ-01`) | the **Needs a location** filter shows **16 of 673** | **DONE** — walked on the demo utility: **6 of 79**. (16 of 673 is the full ten-tenant estate; the shape is the same.) The filter is DECLARED in `PREMISES_FILTERS` — undeclared names are silently dropped, which is `DEF-836`'s shape on this same list |
| **A9** | The equipment map reads a unit's own point where it has one (`PUJ-49`) | a park of twelve cabins shows twelve pins, not one at the site office | **DONE** — and the FILTER had to move with the coalesce: it read `premises__lat__isnull=False`, which excluded a unit with its own point on an unplaced building — the exact case the ruling was written for. The popup names a unit's own point; it stays silent on the ordinary building case |

### Wave B · Creating a property · 8 tasks

| # | Task | Done when | Status |
|---|---|---|---|
| **B1** | The owner becomes optional and every required field is marked (`PUJ-02`) | a property is created with no owner and lands on the **Needs an owner** list | **DONE 2026-09-09** — `2.234.7`. Walked: `POST /premises` with no owner answers **201** and takes `P-00080`; the identical call answered `422 VAL-001 metering.premises.owner_required` on field `owner_id` before. ⚠ After the reversal the street address is the ONLY answer the server insists on, so the form says that in one sentence instead of marking eighteen boxes. **`B1` shipped in the same commit as `B2` — CR-089 §2.1 says they are one change and the rollback in §8 is the only one that is not free** |
| **B2** | The master account is linked, and the dead tile goes (`PUJ-11`) | the header shows *Creekside Holdings LP · master account A-10442* as a link; with none it reads *Needs an owner* and offers **Find** | **DONE 2026-09-09** — `2.234.7`/`2.234.12`. ⚠ **THE FIGURES IN THIS ROW ARE ILLUSTRATIVE AND ONE OF THEM CANNOT EXIST**: there is no *Creekside Holdings LP* and no `A-10442`, and **0 of `brazosbend`'s 5 owner records had ANY master account**, so the linked case had to be created through the product's own endpoint before it could be walked. Walked, all three: `P-00001 · 1408 Bluestem Ln` reads **Needs an owner**, keeps its free-text name and offers **Find an owner** — pressed, searched, attached `Ridge Property LLC`, and the cell re-rendered; `P-00043 · 181 Willow Bend Dr` reads *Silver Creek Duplex Holdings · Landlord* with **Account `AC-2026-00001` AS A LINK** to `/brazosbend/accounts/<id>`; `P-00045 · 301 Mill Pond Ln` reads the honest *No account is linked to this owner yet*. **The list**: 78 of 84 need an owner, 6 have one, and an unknown value falls through to 84 |
| **B3** | The owner search says what that owner already owns (`PUJ-02`) | choosing one shows *already owns 3 properties, master account A-10442* | **DONE 2026-09-09** — `2.234.12`. Walked on the real party: choosing *Silver Creek Duplex Holdings* shows **“Already owns 2 other properties here. master account AC-2026-00001”**. Three sentences, not one template with a count in it — *already owns 1 other properties* is copy a clerk stops reading and no catalogue can fix it from one string (B14 rule 35). The account is fetched for the ONE party picked; the list does not expand accounts (`DEF-324`'s N+1) |
| **B4** | Utility services become a searchable multi-select of chips (`PUJ-06` sibling) | all eleven are offered, chosen ones are removable chips, and type-to-filter works | **DONE 2026-09-09** — `2.234.12`. The chips and the multi-select were already there; **type-to-filter was not**, and that is what this task added. ⚠ *all eleven* is a statement about a tenant that SELLS eleven: `BR-MET-003` means the control can only offer the tenant's enabled set, and `brazosbend` sells **two**. Walked: two chips at open, an add-list that is correctly EMPTY while everything is chosen, and after removing two chips, typing *Electric* adds it back |
| **B5** | Common areas can be recorded while creating (`PUJ-05`) | *Laundry* and *Corridor lighting* are added on the form and named on the review | **DONE 2026-09-09** — `2.234.12`. Walked: *Laundry* and *Corridor lighting* typed on the form, both named on the review, both created. ⚠ A common area IS a unit (`unit_type: common_area`), so they join the create's nested `units` list and land in the SAME transaction (`BR-SHL-019`) — no second endpoint and no half-made building when one is refused |
| **B6** | Route and cycle are settable at creation and always shown (`PUJ-06`) | the header reads *Route 12 · Cycle 3 — bills on the 12th*; with neither it reads *No route yet* | **DONE for CREATION and for the READ; the *bills on the 12th* half is NOT built.** `2.234.12`. ⚠ **`route` WAS ALREADY ON THE CREATE PAYLOAD'S TOLERATED-KEY LIST WITH NO CONSUMER** — `{"route": "COMPLETE NONSENSE, NOT A ROUTE"}` answered **201**, `P-00081`, `routes_joined []`. Filed `DEF-MET-4715`, now refused BY NAME. Walked: the picker draws the PAIR on one line (*Route RT-002 · Cycle CY-002* — real codes; there is no *Route 12*), the create joins the building's units, and `GET /premises/{id}` serves `routes`. **What is owed: the cycle's bill DATE.** The read serves `cycle_code` and `cycle_name` and no due day, so *— bills on the 12th* is not rendered anywhere. ⚠ **The route is READ-ONLY on the edit form and that is deliberate**: changing one afterwards is `BR-MET-074`'s MOVE, which CR-006 requires be confirmed on screen |
| **B7** | The review shows every answer, and the numbers the series will take (`PUJ-07`, `PUJ-08`) | all sixteen answers appear, absences included, with *Premise number · P-00080* and *Unit numbers · U-01144 to U-01147* | **DONE 2026-09-09** — `2.234.12`. **Sixteen rows where there were four**, absences included: property type and inside-city-limits — *the two that decide how it bills* — were both missing before. Walked: the real numbers are **`Premise number · P-00084`** and **`Unit numbers · U-00004 — U-00006`** (`U-01144` is an illustration; `brazosbend` numbers most of its units `SCW-U-###`). ⚠ **THE PREVIEW CAUGHT THE COUNTER UP UNCONDITIONALLY AND THE ALLOCATOR ONLY DOES SO ON COLLISION** — a sibling hit the identical bug on the unit series the same hour (`DEF-MET-4719`), and this premises twin now follows THEIR loop rather than being a second idea about one question. My first test for it PASSED against the bug; it now builds the one discriminating state and goes red |
| **B8** | Create and edit are the same screen, and a refusal is fixable where it happens (`PUJ-18`, `PUJ-09`) | both forms carry the same six headings in the same order; a refused create names the field and focuses it | **DONE 2026-09-09** — `2.234.12`. Six headings on both forms, declared ONCE in `premisesFormSections.tsx` and mapped by both, so this is structural rather than two files agreeing by convention: *Where it is · Parcel and map point · What kind of property · Area, route and cycle · Utility services · Owner*. They did NOT match before — the create asked for the parcel and the point FOURTH and the edit form LAST, and neither had a heading of any kind. `PremisesFormSections.test.tsx` reads both sources and was proved RED by re-pointing one section. **The refusal**: a bad latitude now walks BACK to step 2, focuses `#lat`, scrolls it into view, keeps every other answer, and says *“Check Latitude — the rest of your answers are still here.”* |

### Wave C · The property's tabs · 6 tasks

| # | Task | Done when | Status |
|---|---|---|---|
| **C1** | The Units tab carries what each unit owes (`PUJ-12`) | *Unit 1 · 61.40* and *Unit 4 · 0.00 · Vacant — base charges bill to the owner*, right-aligned and tabular | **DONE 2026-09-09** — walked on `brazosbend`: `P-00039 · 301 Mill Pond Ln` draws `Apt 101 · $362.61` · `Apt 103 · $90.18` · `Apt 106 · $181.32` · `Apt 104` and `Apt 105` at `$0.00`, right-aligned and tabular. ⚠ **THE `0.00` ON THE VACANT ROW IS NOT BUILT AND THAT IS DELIBERATE:** `owed_for_units` resolves the OCCUPYING account, so a vacancy is not measured at all and a unit whose tenant left still owing has a CLOSED account the map excludes — a manufactured zero there is `DEF-138` word for word. `Apt 102` reads *Vacant — base charges bill to the owner* and no figure; the reasoning is in the decision log. A common area reads *It is always billed to the owner's account* instead (`BR-MET-101`). The money is wave `E1`'s `owed_for_units` seam, and this lane DELETED its own per-unit `unit_owed()` to use it |
| **C2** | Common areas can be added from their own tab (`PUJ-13`) | **+ Add a common area** is on the tab, and the empty state offers it | **DONE 2026-09-09** — **+ Add a common area** is on the tab and in its empty state, disabled with its reason for a role that may not write. Walked: pressed on `P-00039`, `Bike store 10735` created through `POST /units` with `is_common_area: true` (`BR-MET-101` — a common area IS a unit with a flag) and found on the tab afterwards. It is deliberately NOT the add-units wizard: three fields, because a hallway needs a name |
| **C3** | The Assets tab groups what bills and what does not (`PUJ-14`) | *Meters and sub-meters · 4 · these are what bill* over *Behind the meter · 5 · we own them, they are not read* | **DONE 2026-09-09** — walked on `103 Willow Bend Dr`: *Meters and sub-meters · 2 · These are what bill.* over *Behind the meter · 4 · We own them. They are not read.* The split is the SERVER's own `asset_types.category` (`BR-AST-004`), never inferred from a type code, and a group with nothing in it is ABSENT rather than an empty table under a heading. `Meter type` and `Read method` are dropped from the behind-the-meter table only — `BR-AST-044` binds the S50 DETAIL view, and its own amendment makes `meter_type` unavailable on non-measuring types, so those two columns were structurally empty on every row |
| **C4** | A last-read column that can say **not read** and why (`PUJ-14`) | `FIR-00311` reads *not read — billed on size*; `CRT-08820` reads *not read — billed per cart* | **DONE 2026-09-09** — walked: `E-5001` and `W-5001` read `08/14/2026`; `CART-0001..3` read *not read — billed per cart*; `FS-00002` reads *not read — billed on size*. `last_read` now rides every meter and sub-meter, batched into ONE query by `selectors.asset_page_rows` rather than one per row. ⚠ A behind-the-meter row carries **no `last_read` key at all**, deliberately: `null` there is indistinguishable from *a meter nobody has read yet*. A tenant's own added type falls to the general *not read — we own it* rather than claiming a price rule |
| **C5** | `fire_line` is seeded for every tenant that sells fire (`PUJ-15`, `DEF-AST-4690`) | on `brazosbend`, **Fire service line** is offered in the inventory picker | **DONE 2026-09-09** — `assets/0013`, insert-if-absent per tenant in its own savepoint. ⚠ **THE DEFECT'S OWN EVIDENCE WAS ONE TENANT OUT OF DATE:** measured 2026-09-09, `brazosbend` HELD the row (created 2026-09-08 18:45 as a side effect of unrelated traffic — `ensure_reference_catalogs()` heals lazily), and `oak-ridge` and `silver-creek-water2` still held nine behind-the-meter types. After the migration all ten tenants hold ten. Walked: the picker offers **Fire service line** on `brazosbend`, and `FS-00002` (size `FL-6`) was tagged for real on `103 Willow Bend Dr`. Unconditional rather than gated on the enabled services, because gating re-opens this defect the first time a utility turns fire on — recorded in the decision log |
| **C6** | The work-orders tab answers *when is somebody coming*; audit rows show the old value without a press (`PUJ-16`, `PUJ-17`) | *Meter change · Thursday 10 Sep · A. Reyes*; and *Owner · none → Creekside Holdings LP* on the row itself | **DONE for the AUDIT half; the WORK-ORDERS half is BUILT AND NOT WALKED, and that is stated rather than glossed.** Audit, walked on `P-00039`: *Services available · 2 recorded → 5 recorded* on the row, **zero expand controls left in the table**. It costs no request — `audit_page(..., with_values=True)` serves the pair on an ENTITY-SCOPED read from columns the page already had, and the unfiltered S61 list is byte-identical. Work orders: **When** and **Who** columns added, an appointment window and an SLA deadline served as separate keys and drawn differently (a window is what a customer was promised; `due_at` is `BR-WRK-018`'s internal deadline). ⚠ **NO WORK ORDER EXISTS ON ANY SAMPLE PROPERTY**, so those two columns have never rendered a row in a browser — only the honest empty state was seen. Covered by `buildViews.test.tsx` (4 cases), which is not the same as having been seen |

### Wave D · Taking a thing out of service · 2 tasks

| # | Task | Done when | Status |
|---|---|---|---|
| **D1** | A property can be taken out of service (`PUJ-21`, `BR-MET-1164`) | the refusal shows *4 active units · 9 attached assets · 3 open accounts*, each linked, and holds on *Close the accounts first* | **DONE 2026-09-08** — walked on `brazosbend`: `P-00037 · 181 Willow Bend Dr` draws *2 active units · 4 attached assets · 2 open accounts · 1 unit still owes*, each a link, the commit held on *Close the accounts first*; the same transition posted past the screen answers 409. `P-00052` was then taken out of service for real and put back |
| **D2** | A unit can be taken out of service (`PUJ-48`) | the refusal shows *1 open account · 2 attached meters* and holds on *Close the account first*; a date and a reason are required | **DONE 2026-09-08** — walked: the unit's dialog draws *1 open account · 2 attached assets* and holds on *Close the account first*. ⚠ **THE WORD IS ASSETS, NOT METERS, AND THAT IS THIS PO's OWN RULING OF THE SAME DAY** (*"Meter = assets"*, fourth round §3): the count links to the unit's **Assets** tab, and *meters* would send a clerk to a tab that does not exist. Recorded in the decision log |

### Wave E · Creating units · 6 tasks

| # | Task | Done when | Status |
|---|---|---|---|
| **E1** | The units list is scanned by address and carries money (`PUJ-22`) | **Address** is the second column, the label leads over `U-01144`, and **Owed** reads `61.40` | **DONE 2026-09-09** — walked on `brazosbend`: the columns read `Select · Address · Unit · Type · Services · Meters · Occupant/Account · Owed · Status`, the cells read *101 Silver Creek Rd* over `P-00007` and *Unit 1* over `SCW-U-001`, and Owed reads `$158.10 · $225.46 · $174.02 · $1,202.40 · $0.00 · $385.11`. The figure is `_balance_cells`' own, forwarded — the accounts list, the S21 header, the unit's Account tab and this column are one derivation grouped four ways. ⚠ Nothing is REMOVED: `label` joins `occupancy` in the column chooser, both still sortable |
| **E2** | A building's address finds its units (`PUJ-50`) | typing *412 Cypress Row* into the units list returns the four units there | **DONE 2026-09-09** — walked: *Kestrel Park ph. 2* returns its **12 of 133**, every row at that address. ⚠ **THE SERVER HALF WAS ALREADY BUILT** — `units_list` has matched `premises__address_line__icontains` all along and the placeholder already said *Search unit, address, premise # or meter #…* — so what this wave adds is the PROOF (nothing asserted it) and the column that makes the answer readable |
| **E3** | Adding units starts by naming the building (`PUJ-23`) | from the units list, searching *412 Cypress* shows the building's number, type, status, *1 unit today, numbered 1*, route, cycle, owner and services | **DONE 2026-09-09** — `AddUnitsWizard`, its own screen at `/premises/units/new`; `UNITS_ADD_ROUTE` re-pointed. Walked: typing *Kestrel Park* offers `P-00067 · Kestrel Park ph. 2` and the card reads its type, its status, *Units today*, *Services available*, *Route and cycle* and *Owner / manager*. The routes come from `services._routes_a_premises_is_on` — the function the create actually cascades through (`BR-MET-083(b)`), never a screen-only second reading |
| **E4** | The plain case is plain; the pattern generator folds away (`PUJ-24`) | *3* and *2* typed, **Continue →** pressed, and the `{floor}`/`{seq:00}` tokens are behind one line | **DONE 2026-09-09** — walked: two numbers typed, Continue pressed, and `label_pattern` is not on screen until *Name them differently* is opened. ⚠ **AND THE DEFAULT PATTERN MOVED**, which is the half that made the plain case unplain: it was `Apt {floor}{seq:00}`, so three flats came out `Apt 101, Apt 102, Apt 103`. It is `{seq}` now and they come out `1, 2, 3` — verified on the created rows |
| **E5** | A plan can be attached at creation, optionally (`PUJ-25`, `BR-MET-007`) | picking *Residential Standard* shows it on all three preview rows; blank reads *Set the plan when somebody moves in* | **DONE 2026-09-09** — walked: the picker offers *Set the plan when somebody moves in* first and then every published plan; the chosen plan is on all three review rows and all three created units came back with a `rate_plan_id`. ⚠ **THE CONTRACT WAS ALREADY SIGNED AND ONLY THE PANEL WAS MISSING** — `create_unit` has accepted a nested `plan` block since S16; the generator now carries it through |
| **E6** | A review step before anything is written (`PUJ-26`) | step 2 lists the building, what it lends, the three labels, `U-01145` to `U-01147`, *Floor · Not recorded*, and commits on **Create 3 units ✓** | **DONE 2026-09-09** — walked end to end on `brazosbend`, three times, with three different buildings. The rail reads *1 Building and how many · 2 Review*; the review names the building, the three labels `1`, `2`, `3`, the three numbers, *Floor · Not recorded*, and commits on **Create 3 units ✓**. ⚠ **THE NUMBERS ARE NOT `U-01145`–`U-01147` AND WERE NEVER GOING TO BE — §6's correction above applies here exactly.** What must be true is the RULE, not the figures, so it was proved with whatever the series actually issued: `U-00004`–`U-00006`, then `U-00007`–`U-00009`, then `U-00010`–`U-00012`, each time read off the RENDERED review before the press and compared with the `unit_no` values the server handed back afterwards. ⚠ **`BR-MET-1165` IS NOW IN THE METERING RULES** — the blueprint held it and the repository did not, and `B7` needs it too. ⚠ **AND THE FIRST IMPLEMENTATION OF IT WAS WRONG (`DEF-MET-4719`): the review printed `U-00421` and the create issued `U-00001`**, with every test green. Found by the browser walk and by nothing else. |

### Wave F · The unit's page · 6 tasks

| # | Task | Done when | Status |
|---|---|---|---|
| **F1** | The unit's Overview carries its number (`PUJ-29`) | the header reads `U-01145 · 412 Cypress Row, Silver Creek, TX 78611` | **DONE 2026-09-09** — walked on `brazosbend` at `1408 Elm Street`: the Overview's FIRST fact is now *Unit ID · SCW-U-201*, ahead of the premise. ⚠ **THE NUMBER WAS ALREADY IN THE H1** (`SCW-U-201 · Apt 101`) and in four other places; what was missing was the one panel headed *Overview*, which is where a person looks for a unit's facts. `B14` rule 31 does not reach it — `unit_no` is `BR-MET-1165`'s SERIES number a clerk quotes on the phone, not a database id |
| **F2** | An occupied unit shows its account (`PUJ-28`) | *Account · A-10517 · M. Alvarez · Active · since 1 Jun 2026* over *Owes $61.40, due 24 Sep · deposit $150.00 held · autopay on*; vacant names the owner's account | **DONE 2026-09-09** — walked at `1408 Elm Street`: *Account · **A-10432** · Miller, Sarah* (the number LEADS and it is a link) · *Status · Active · since 02/05/2024* · *Balance · **$247.30***, *Deposit held · **$150.00** · taken 02/05/2024*, *Autopay · On — the account is not cash only, so it will be taken*, and **Open the account tab →**. It reads wave I's `GET /units/{id}/account` under the SAME query key the Account tab uses, so moving Overview → Account cost **0 requests** (measured). ⚠ **THE DUE DATE IS A STATED ABSENCE AND NOT AN INVENTED DATE** — `BR-CUS-033` makes it the OLDEST STILL-OPEN bill's, and no module publishes which bill is open; the account header's own sentence is reused rather than a second one worded. A vacant unit draws *Base charges bill to the owner* and names the owner's account where one covers it |
| **F3** | The four KPI tiles appear on all six unit tabs and all six property tabs | **Assets · Owed · Plan · Open work** are on every unit tab; **Units · Assets · Owed here · Open work orders** on every property tab | **DONE FOR THE UNIT'S SIX; THE PROPERTY'S FOUR ARE NOT AND THAT IS STATED (`DEF-MET-4730`).** Walked: `Assets 2 · 2 bill · 0 behind the meter` · `Owed $247.30` · `Plan Sample — Residential v1` · `Open work 0`, on all six tabs, and `Open work 1` on `SCW-U-307`, which carries a planned job. ⚠ **THE PLACEMENT HALF WAS ALREADY TRUE — the strip has rendered outside the tab bodies since `US-SHL-020`; what was wrong was the TILES** (`ACCOUNT · PLAN · METERS · SINCE`). ⚠ **AND THE COST WAS MEASURED RATHER THAN ESTIMATED, per §5:** all three new figures ride `GET /units/{id}`, so the tiles cost **zero extra requests on load and zero on every one of the five tab changes**; what they cost is three queries on that one endpoint, and `unit_list_dict` is untouched so the 133-row units list pays nothing. The property's tiles still read `Units · Occupied · Meters · Master account` — `PremisesDetailPage.tsx` is wave C's file and this wave may not restructure it |
| **F4** | A vacancy is a row on the occupancy tab (`PUJ-42`) | *Vacant · 28 May to 1 Jun 2026 · 4 days · base charges billed to the owner* between the two tenancies | **DONE 2026-09-09** — walked on `SCW-U-042 · 301 Mill Pond Ln`, whose tenancy closed on 31 Jul 2026: *Vacant · — · **08/01/2026** · Current · **40 days** · Base charges bill to the owner.* Derived from the tenancies either side; nothing is stored. ⚠ **THE WORKED FIGURE IN THIS ROW IS ONE DAY LONG AND THE ROW DRAWS THE TRUE NUMBER.** `customers.services` bills a leaver THROUGH `moved_out_on` and writes that date to `closed_at`, so a tenancy closing on the 28th OCCUPIED the 28th: the gap is 29–31 May, **three days**, not four. §6's correction block already says the figures are illustrations; this one has an off-by-one in it. ⚠ **AND THE ROW DOES NOT SAY WHICH FIGURE IS BILLED** — `OQ-316`'s remaining word (base-only vs full) is still open, so the absence narrowed rather than went |
| **F5** | The unit's audit tab draws its rows (`PUJ-43`) | *1 Jun 2026 · D. Whitfield · Plan set · none → Residential Standard*, not a sentence pointing elsewhere | **ALREADY DONE BY WAVE C, VERIFIED HERE, AND NOTHING WAS BUILT.** The unit page mounts the SAME `AuditTab` wave C fixed on the property (`C6`), so its fix arrived on this screen the moment it landed. Walked: *09/08/2026 13:27 · Dana Whitfield · **Plan assigned to a unit** · Plan name **Not set → Sample — Residential*** on the row, with **zero expand controls** in the table. ⚠ **THE EVIDENCE IN THE BRIEFING WAS STALE** — it reported an empty tab; measured 2026-09-09, **every one of `brazosbend`'s 131 units carries audit rows** and none can reach the empty state. The check is in the walkthrough so a regression names itself |
| **F6** | A unit has an edit screen, and its plan is applied or changed from it (`PUJ-44`, `PUJ-45`) | **✎ Edit** on the unit's page changes the label to `2B` and the floor area to `820 sq ft`; the same form carries *Plan* and *The change takes effect* | **DONE 2026-09-09** — `✏ Edit` is on the unit's header beside Move, and walked: the label and `820 sq ft` were written and read back, and the plan was moved from *Sample — Residential* to *Industrial* THROUGH THE FORM and read back from the server. ⚠ **THE PLAN RIDES THE SAME `PATCH /units/{id}` IN ONE TRANSACTION**, so a refused plan takes the label change back with it. ⚠ **AND `plan` WAS ALREADY ACCEPTED ON THAT ENDPOINT AND SILENTLY DROPPED** — `_validate_unit`'s `ignored` set has carried it since S16 and nothing read it on a PATCH, so a form like this one would have answered 200 and changed nothing about the plan, forever. ⚠ Two things are stated rather than hidden: the list keeps a private copy of the form (`DEF-MET-4731`), and the first build drew a BLANK plan picker on a unit that has a plan (`DEF-MET-4732`, `DEF-442`'s mechanism a third time) — found by reopening the form in a browser and by nothing else |

### Wave G · Assets on a unit · 3 tasks — **ALL THREE DONE 2026-09-09 (`2.234.15`)**

| # | Task | Done when | Status |
|---|---|---|---|
| **G1** | The inventory search takes what a clerk is holding (`PUJ-30`) | searching *5/8 water depot* shows chips **Water ×** and **In the depot ×** and lists the matching meters | **DONE 2026-09-09** (`2.234.15`). Walked on `brazosbend` / `SCW-U-001 · Unit 1`, 101 Silver Creek Rd. Typing **5/8 water meter inventory depot** returns three chips — **Water 5/8"**, **Inventory**, **Meter** — and the two spares that match; pressing a chip's ✕ takes exactly the words it ate back out of the box. `GET /assets?terms=` reads the text against FOUR of the TENANT's own catalogues (asset types · meter classes · lifecycle stages · ratified size classes) and serves the reading BESIDE the rows it filtered by, because two routes could draw one and filter by the other forever with nothing red (`BR-MET-1165`'s lesson). `BR-AST-531` is the rule, given a home today. ⚠ **THE WORD `depot` IS NOT A CHIP AND THAT IS THE ANSWER, NOT A MISS.** No tenant anywhere names a lifecycle stage that; *Inventory* is the word this product and this catalogue already use, and a synonym table would be English exported to ten other catalogues (B14 rule 35). The word is SAID BACK — *Not one of your words: depot* — rather than dropped. ⚠ **AND SERVICE IS DELIBERATELY NOT ONE OF THE FAMILIES**: an asset's service resolves through its SERVICE POINT and a shelved asset has none, so `f.service` could only ever return nothing here — law 7's *incapable of passing* as a feature. The service word lands through the size class, which is NAMED for it. ⚠ **TWO DEFECTS FOUND ON THE WAY, BOTH FIXED:** `DEF-AST-4734` — `f.assigned=false` was accepted and IGNORED, answering **142 rows where 10 are unattached**; `DEF-AST-4735` — no seeded inventory spare has ever recorded its connection size, so `5/8` matched nothing anywhere and this task was undemonstrable on the product's own demo |
| **G2** | Assigning finishes on the unit (`PUJ-31`) | **Assign ✓** on a row puts the meter in the unit's table above, without opening the asset's own reassign page | **DONE 2026-09-09** — walked: `W-5100` attached to `SCW-U-001 · Unit 1`, 101 Silver Creek Rd, the URL never left `/premises/units/…`, and `GET /units/{id}` listed it a second later. It used to NAVIGATE to `/assets/:id/reassign?unit=<this unit>`. ⚠ **THE UNIT'S OWN PAYLOAD IS INVALIDATED WITH THE REGISTRY ANSWER**, because `unit.meters` is the SPINE of the table above — invalidating only the registry would leave the new row invisible until a reload, which is an assign that looks like it did nothing. ⚠ **THE BUTTON IS GATED ON THE ROW'S OWN `actions`** (BR-AST-006), never on a rule copied onto the screen; a row the server would refuse keeps the button and reads *Not free to assign*. `BR-AST-532` |
| **G3** | An attached asset's status changes from its row (`PUJ-32`) | the pencil on `MTR-40218` changes *In service* to *Removed* with a date and reason, without leaving the unit | **DONE 2026-09-09** — there was no way to do this from the unit at all: the tab drew a status column and offered no control anywhere on the page. Walked: `W-5000` at `SCW-U-001 · Unit 1` moved **Installed → Needs repair** on 8 Sep 2026 with *Register glass cracked at the meter pit*, without leaving the unit, and it was STILL on the unit afterwards — a status change is not a removal. ⚠ **IT POSTS `POST /assets/{id}/maintenance`, WHICH IS WHERE A STATUS CHANGE LIVES** — BR-AST-018 makes the entry append-only, BR-AST-020 makes the target legal from the current stage only, and the endpoint takes the date and the reason WITH the stage. A `PATCH` of the column would have skipped all three. ⚠ **TWO DEPARTURES FROM THE EXAMPLE, BOTH DELIBERATE:** *Removed* is not a lifecycle stage anywhere in this product — it is one of `BR-AST-021`'s four RETIRE reasons — and **retiring is not offered here at all**, because BR-AST-030 makes it terminal and BR-AST-032 makes it the System Admin's own wizard with a reason, a date and a book-value treatment; a one-click irreversible act does not belong on a screen about a flat. What the form offers is `legalTargets`, which on the seeded stages is exactly ONE move from *Installed* and says so. `BR-AST-532` |

### Wave H · The plan screen · 3 tasks

| # | Task | Done when | Status |
|---|---|---|---|
| **H1** | One date format, with a named month (`PUJ-33`, `DEF-MET-4689`) | every date on the tab reads *1 Jun 2026*; the picker reads *Showing what applies today, 8 Sep 2026* | **DONE 2026-09-09** (`2.234.11`). Walked on `brazosbend` / `SCW-U-001 · Unit 1`, 101 Silver Creek Rd — tenant format `MM/DD/YYYY`, which is what made `06/01/2026` ambiguous. **Four shapes became one:** *Effective from* `06/01/2026` and the panel's `2026-06-01` both read **1 Jun 2026**, and the period line reads **1 Sep 2026 to 30 Sep 2026**. ⚠ **A NATIVE `<input type="date">` RENDERS IN THE BROWSER'S OWN LOCALE AND NO API CAN CHANGE THAT**, so each box carries a named-month line beneath it — not `regionalDateEcho`, which prints the TENANT format and would have kept a fourth shape. `BR-MET-1167` is the rule, given a home today. ⚠ **THE `ON PLAN SINCE` TILE IS NOT FIXED**: it is the KPI strip, wave F's region, being rewritten as this landed — `DEF-MET-4725`, with an **expiry check** in the walkthrough that goes red the day wave F fixes it |
| **H2** | One floor sentence, and eligibility written for a clerk (`PUJ-34`, `DEF-MET-4693`) | *No floor is set — a bill can be any amount, including nothing* appears once, six services read *none*, and eligibility reads *Not checked — no plan on this system asks for proof yet* | **DONE 2026-09-09**. The sentence appears **once**, on the plan's own Minimum bill row, and every other floor cell reads **none** — a NEW key rather than a reword, because `rating.planDetail.field.minimumBillAbsent` is `PlanDetail`'s too and that screen prints it once where it is right. Eligibility reads *Not checked — no plan here asks for proof before it applies*. ⚠ **THE WORDING MOVED FROM THE DONE-WHEN ON PURPOSE:** the row is a CONSTANT, not a read of this plan's `eligibility` column, so it is worded to be true of every tenant — nothing turns a stored condition into a requirement (`DEF-404`, `BR-RAT-043`). Naming a plan's own conditions is owed on `BR-MET-1168` |
| **H3** | A zero base says what the service is priced on (`PUJ-35`) | *Fire · 0.00 · By the size of the line, times how many*, *Trash · 0.00 · Per cart, monthly*, *Solar · 0.00 · By capacity* | **DONE 2026-09-09** — a **PRICED ON** column: *Fire · $0.00 · By the size of each one, times how many* · *Trash · $0.00 · same* · *Solar · $0.00 · By capacity — the kW installed*. ⚠ **ONE SENTENCE PER RULED SHAPE AND NOT ONE PER SERVICE**, which is the whole design: the axis is `apps/tenancy`'s ratified size classes resolved on the SERVER (`_service_priced_on`) through `apps.rating.resolution.service_prices_by_size_class`, so **no service is named in the code** and the twelfth lands on whichever side its own rows put it. Three shapes and one absence — capacity · size bands · no size axis · *not ruled* (thermal steam, `OQ-560`). `BR-MET-1166`, given a home today. ⛔ It carries no FIGURE; B4/B5 untouched. ⚠ **NO SEEDED TENANT HAS A ZERO-BASE SERVICE AT ALL** — §6's correction block again — so it was walked after adding three `plan_services` rows at `0.0000` to a private clone; the SQL is in the walkthrough's header, and three zeros move no sum, so the bases still add to the plan's `$20.00` |

### Wave I · The unit's account tab · 6 tasks — **ALL SIX DONE 2026-09-08 (`2.234.2`)**

| # | Task | Done when | Status |
|---|---|---|---|
| **I1** | A protection is a banner above everything (`PUJ-36`, `DEF-CUS-4691`) | the tab opens with *Do not disconnect. Medical certificate, until 11/05/2026 · set by this utility, from 08/07/2026* | **DONE 2026-09-08** (`2.234.2`). ⚠ The author is a **ROLE**: `account_protections.set_by` holds `tenant`/`regulator` and no column holds a person, so no name is invented. The example's *D. Whitfield* is the signed-in demo user, printed by the app frame. |
| **I2** | The customer class is named and says what it decides (`PUJ-37`) | *Class · Residential · Single-family · this decides which base charge the plan applies* | **DONE 2026-09-08** |
| **I3** | Autopay is read together with cash-only (`PUJ-38`) | *On — the account is not cash only, so it will be taken*; `A-10432` says *On — but the account went cash only after 2 bounced payments, so nothing will be drafted* | **DONE 2026-09-08**. The reading is the SERVER's single answer (`payments.autopay.is_enrolled`), never re-derived on the client — `DEF-070`. |
| **I4** | Five money states are stated, not omitted (`PUJ-39`) | all six render, verbatim, and the deposit reads *$150.00 · taken 02/05/2024* on `A-10432` | **DONE 2026-09-08**. Each row has a THIRD state — *could not be read* — because three of them cross a module seam and `None` there is not *none* (`DEF-127`). |
| **I5** | Account notes are on the tab (`PUJ-40`) | *📌 Medical protection* and *Meter access · Dog in the side yard — ring first. · author not on file · 09/08/2026 · Marked customer-visible* | **DONE 2026-09-08**. Two departures from the example, both deliberate: the author is *author not on file* because `author_name` is null on EVERY note in the product (`DEF-CUS-4704`), and the flag uses the account screen's own pill wording (B14 rule 34). |
| **I6** | Something writes the nine empty columns (`PUJ-41`, `DEF-CUS-4692`) | measured on both demo utilities after seeding: **all nine at 1 or more**, from 0 | **DONE 2026-09-08**. `apps/customers/sample_account_flags.py`, called last by `seed_sample_records`, idempotent (a replay writes 0). Six go through the product's own doors; three have **no writing door anywhere** and are named with their reasons in `NO_DOOR`. |

### Wave J · Moving a unit · 3 tasks — **J1 AND J2 DONE 2026-09-09 (`2.234.10`); J3 IS OWED TO BILLING**

| # | Task | Done when | Status |
|---|---|---|---|
| **J1** | The move screen itemises what moving does (`PUJ-46`) | seven consequences, including *the 5 assets tagged to this unit travel with it — their addresses are the building's, so all five change address too* and *Route 12 · Cycle 3 → Route 4 · Cycle 1* | **DONE 2026-09-09** — walked twice on `brazosbend` and the counts below are MEASURED, not the illustrations above. `SCW-U-002` moved `103 Willow Bend Dr` → `412 Cypress Row`: the screen said *All 5 assets tagged to this unit travel with it and take the new address*, and afterwards `CART-0001`, `CART-0002`, `CART-0003`, `E-5001` and `W-5001` all read `412 Cypress Row`. `U-00101-A` moved `1408 Bluestem Ln` → `901 Hillside Ave`: *All 2 assets…*, and both followed. The tier is `danger` (`FormModal` grew `submitVariant`, the same optional shape `ConfirmDialog` took for `DEF-718`). |
| **J2** | A date picker and a human plural (`PUJ-47`, `DEF-MET-4694`) | the date field is a picker showing *8 Sep 2026*; the warning reads *This unit has carried two accounts* | **DONE 2026-09-09** — `(s)` is gone from all eleven catalogues (`_one`/`_other`, and `move_unit` now sends `count` beside `accounts` because that is the parameter the plural is chosen by). The date field is and always was a native picker; what was a format instruction was the SERVER's refusal, *"Enter the date as YYYY-MM-DD"* → *"Pick the date from the calendar."* ⚠ Two departures from the example, both deliberate: the date is the TENANT's format through the one shared formatter — a fifth formatter here is `DEF-MET-4689`, wave H's — and the count is the DIGIT, because spelling numerals is a rule about English and B14 rule 35 forbids exporting it to ten other catalogues. ⚠ *"two accounts"* **cannot be walked anywhere**: measured across all nine seeded tenants, no unit has ever carried more than one account. The `_one` form is what the browser showed; `_other` is asserted in `MoveUnitModal.test.tsx`. |
| **J3** | Bills can be counted for a single unit (`PUJ-55`) | the move screen reads *Bills it has produced · 14* instead of *Cannot be counted* | **NOT DONE, AND OWED TO BILLING — the hold is WIRED rather than described.** `DEF-511` is still open: nothing counts issued invoices by unit, and the ONE function that would (`.count()` of the queryset `billing.selectors.last_issued_bill_for_unit` already writes) belongs to `apps/billing/selectors.py`, another lane's this session. `seams.issued_bill_count_for_unit` DECLARES that contract, resolves it at call time and is parked in `seam_known_gaps.txt`; the day it lands the number appears with no change in metering and none on the client. `None` is served for *nobody could count them* and never `0`, which would read as *this unit has never billed*. Both sides are asserted in `test_cr089_j_move_preview.py` and `MoveUnitModal.test.tsx` so nobody can publish half of it. |

### Wave K · Finding by address · 3 tasks

| # | Task | Done when | Status |
|---|---|---|---|
| **K1** | An address finds the accounts at it (`PUJ-51`) | typing *412 Cypress Row* into the accounts list returns `A-10517` and the others at that building | **DONE** — and *the others* turned out to mean **the owner**. The accounts list already searched an address through `unit_ids_matching`, which walks *unit → premises*, so it found every OCCUPANT and dropped the one account with no unit: `BR-CUS-1010`'s Master Account, which hangs off the ADDRESS. On the demo utility *500 Main St* returned **five of six** and left out **`AC-2026-00051`, the account that owns the building**; it returns all six now. ⚠ **THE DONE-WHEN'S OWN EXAMPLE CANNOT BE DEMONSTRATED ON THIS FIXTURE AND THAT IS §8'S WARNING COMING TRUE:** `412 Cypress Row` is real (`P-00080`) and has **one unit and no accounts at all**, and **`A-10517` does not exist**. Demonstrated instead on the addresses that carry data |
| **K2** | An address finds the payments made at it (`PUJ-52`) | the same search on the payments list returns the payments taken against those accounts | **DONE** — the payments list searched no address at all. *301 Mill Pond Ln* returned **0** while **nine** payments stood against the six accounts there; it returns **9** now. The prompt names the address in all eleven catalogues, because a clerk does not type a street into a box that does not offer to search one |
| **K3** | An address finds the bills raised at it (`PUJ-53`) | the same search on the bills list returns `BL-2608-000052` and every other bill at that building | **DONE** — the largest gap, exactly as §6 said: a bill knows its account, the account knows its property, and no search crossed that. *301 Mill Pond Ln* returned **0** while **eighteen** bills stood there; it returns **18** now. ⚠ **`BL-2608-000052` IS REAL AND IS NOT AT 412 CYPRESS ROW** — it belongs to `AC-2026-00001` at **101 Silver Creek Rd**, so the done-when was honoured at that address: typing it returns `BL-2607-000001`, **`BL-2608-000052`** and `BL-2608-000101`, which is every bill at that building |

**55 specifications across 11 waves. 9 + 8 + 6 + 2 + 6 + 6 + 3 + 3 + 6 + 3 + 3 = 55.**

---

## 7 · VERSION

`<release>.<change>.<fix>` — this is a **change**, so the middle number moves.

| When | Version |
|---|---|
| At the first wave that lands | `2.234.0` |
| Each later wave | the fix number, `2.234.1`, `2.234.2`, … |
| A defect fixed inside a wave | the fix number, in the same commit as the fix |

Allocated through `10-scripts/allocate.py version --bump change` **at the moment
the first wave pushes**, not now — a version taken early is a version another
lane can take while this one is being written.

⚠ **The gate refuses a CR marked done with no version.** This row exists so that
cannot happen.

---

## 8 · CLOSE — and the rollback, stated before shipping

⚠ **WAVE D LANDED FIRST, SO IT TOOK THE VERSION** — `2.234.0`, allocated
through `10-scripts/allocate.py version --bump change` at the moment it pushed,
exactly as §7 says. Waves A and I take the fix number from here.

### The rollback, per wave

| Wave | How it comes out |
|---|---|
| **A** | The two unit columns are additive and nullable; reverting the frontend leaves them unread and harms nothing. **`g85`'s allow-list must be reverted with them**, or the guard passes over a home it should refuse. |
| **B** | The owner requirement is one server check. Restoring it makes any owner-less property created meanwhile **unsaveable on edit** — so the restore must be paired with either a backfill or a PATCH exemption. **This is the only wave whose rollback is not free, and it is named here rather than discovered.** |
| **C, F, G, I, J, K** | Read-only screen changes. Revert the frontend; nothing written differently. |
| **D** | New status transitions. Reverting leaves properties and units already deactivated **with no screen that can reactivate them** — so the revert must keep the reactivation half. |
| **E** | The wizard gains a step. Reverting mid-flight loses an in-progress draft, which is a nuisance and not a loss: the draft holds no allocated numbers, by `PUJ-08`'s own rule. |
| **H** | Copy and formatting only. Free. |

### The closure bar

**This CR is not closed until a person has done the job on the screen.** Not a
green suite, not a passing gate. Specifically:

1. A property is created from scratch on the demo utility, **with no owner**, and
   appears on the *Needs an owner* list.
2. Its point, parcel and GIS flag are visible on its page.
3. Three units are added to it through the two-step wizard, the review names
   `U-01145` to `U-01147`, and after the press those are the numbers allocated.
4. A meter is assigned to one of them from the inventory, searched by size and
   location rather than by number.
5. That unit is moved to another property, and the seven consequences are read
   before the press.
6. The property is refused deactivation, the blockers are cleared, and it is
   deactivated.

**A defect found on the way is not a CR blocker** — it is filed and the CR
continues, per the standing challenge of 2026-08-19.

### What must be true before wave A starts

* the services-and-UoM lane holding 34 files in the shared tree has landed;
* the demo fixture is re-seeded, or `PUJ-01`, `PUJ-04`, `PUJ-15`, `PUJ-38` and
  `PUJ-41` cannot be demonstrated;
* every wave is dispatched into its own `git worktree`.

---

## Trace

* **Blueprint:** *Premises & Units Blueprint* — 23 screens, 55 specifications,
  81 absences resolved three ways (55 newly specified, 18 folded, 8 out of
  scope), six-table appendix.
* **Decision log:** 2026-09-08, four Premises & Units sections (four rulings,
  then eight, then eight, then twelve), plus *Three rules the blueprint holds and
  the repository does not*.
* **Business rules:** `BR-MET-1161` (amended), `BR-MET-1162`, `BR-MET-1163`,
  `BR-MET-1164`; `BR-MET-045`, `BR-MET-007`, `BR-MET-071` re-cited unchanged.
* **Defects:** `DEF-MET-4689`, `DEF-AST-4690`, `DEF-CUS-4691`, `DEF-CUS-4692`,
  `DEF-MET-4693`, `DEF-MET-4694`.
* **Out of scope, each with its ruling:** import (*"import is sorted"*), the
  draggable map pin (*"we dont need this right now"*), the worked example month,
  backfilling 673 parcel numbers, work/workflows/expanded assets, and a
  per-service plan on one unit.
