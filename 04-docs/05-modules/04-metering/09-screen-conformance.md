# Metering · the DRAWN specification for every Premises & Units screen

**This file exists because a screen drifted from its drawing and every check passed.**

On 2026-09-09 the Product Owner opened the property Overview and found it did not
match the design we had agreed. It was missing three rows entirely (*Read route*,
*Billing cycle*, *Common areas*), used four different labels, rendered one column
as two, drew services as letter badges instead of words, and carried the wrong
four tiles. `tsc` was clean, every suite was green and every gate passed.

**The cause was not a lane's care. It was structural:** CR-089's task rows are
written as *what a person can do and see* — behaviour — and the lanes were
dispatched with those sentences. The layout, the labels, the row order and the
provenance clauses lived only in a walkthrough document that no lane was given.
Three of the agreed labels — `Read route`, `Managed by`, `placed by the address
lookup` — exist nowhere in the product to this day.

**So this file is the drawing, in the repository, in a form a brief can quote and
a check can read.**

## Where these drawings come from — the source of record

**THE SOURCE, NAMED BY THE PRODUCT OWNER ON 2026-09-09:**

> **https://claude.ai/code/artifact/0d988b7d-aebf-476c-846b-bb635200f336**
> *Premises & Units Blueprint* — 23 screens, 55 specifications, 81 absences resolved.

**That page is the drawing for every Premises & Units screen.** It carries all 23 screens as agreed over four rounds of screen-by-
screen review, alongside the specifications, the stated-absence register and the
appendix.

⚠ **THE DRAWINGS LIVED NOWHERE A BUILDER COULD READ THEM, AND THAT IS MOST OF
THE EXPLANATION FOR THE DRIFT.** The blueprint is a published page and a file in
a scratch directory. Neither is in this repository. The design existed, it was
agreed screen by screen, and no lane could open it. **This file is the fix: the
drawings, extracted, in the tree.**

**Extraction verified against the LIVE PAGE, not a local copy.** On 2026-09-09
the published artifact was read back and the drawn frame of all 23 screens
hashed against the copy this file was generated from: **23 identical, 0
differing.** The same check was run against the earlier walkthrough the
blueprint was carved from: **23 identical** again.

**Extraction verified, not assumed.** The blueprint was itself built by carving
the screens out of the earlier walkthrough document, so both hold the same
drawings — checked on 2026-09-09 by hashing the drawn frame of all 23 screens in
each: **23 byte-identical, 0 differing.** Either document yields this file; the
blueprint is the one to cite, because it is the one the PO reads.

**When the blueprint changes, this file changes in the same commit.** A drawing
agreed in review and not extracted here is a drawing no lane will build.

⚠ **Every worked value below is an ILLUSTRATION**, carried over from the
walkthrough — see CR-089 §6's correction block: `A-10517` exists on no tenant,
`BL-2608-000052` exists on eight, and `412 Cypress Row` carries no accounts.
**The labels, the order, the column count and the presence of each row are the
specification. The values are not.**

## How to use it

* **Dispatching a lane:** quote the screen's section into the brief. Do not
  paraphrase it into behaviour sentences — that is the mistake this file records.
* **Building:** the fact rows are an ordered list. Row order, row presence and the
  exact label are all part of the design.
* **Checking:** a browser walkthrough asserts each label is on screen, in order.
  Nothing in this repository reads rendered output, so this is the only thing
  standing between a screen and its drawing.
* **Changing it:** a divergence agreed with the PO is written HERE, dated, with
  the ruling — never left as a silent difference between the product and this file.


---

## P1 · The property list

`S14 · PRM-01` — Premises → Premises


**Header** — eyebrow `Premises & Units` · title `Premises`  
sub-line: Every property that takes service, and the units inside them.


**Actions**, in this order: **↑ Import** · **+ New premise** *(primary)*


**Tabs**: Premises | Units | Imports


**Table columns**, in order: `Premise ⇅` · `Address ⇅` · `Type` · `Units` · `Services` · `Owner` · `On the map` · `Status` · *(no header — row actions, icons)*


**Footer**: Showing 1–50 of 673 · Rows per page 50 ⇤ ← Page 1 of 14 → ⇥


**Rules it must obey**: Table type is one size throughout. Row actions are icons with tooltips, never text links, two visible and the rest behind an overflow. A pagination footer on every list. A property number a clerk reads down the phone is a printed reference and is shown; a database id never is.


---

## P2 · Add a property · Details

`S16 · PRM-07` — Premises → New premise → step 2


**Header** — eyebrow `Premises & Units` · title `Add a premise`  
sub-line: One property, with its first unit if you want one.


**Actions**, in this order: **Cancel** · **Save draft & exit** · **Mark checked** · **✎ Change these** · **Change** · **← Back** · **Continue →** *(primary)*


**Rules it must obey**: Required fields carry the asterisk on the label, and only the ones the server will actually insist on. A multiple choice is chips plus an add control, never a wall of tick-boxes, and five or more options are searchable. Colour is never the only signal — every state carries its word. Built in the shared utility classes, adding nothing to a stylesheet.


---

## P3 · Add a property · Review & save

`S16 · PRM-07` — Premises → New premise → step 3


**Header** — eyebrow `Premises & Units` · title `Review & save`  
sub-line: Everything you have entered. Nothing is written until you press Create.


**Actions**, in this order: **Cancel** · **← Back** · **Create premise ✓** *(primary)*


**Fact rows** — 17, ONE column, in this order:

| # | label | value as drawn |
|---|---|---|
| 1 | **Premise number** | P-00080 · the next in this utility's series |
| 2 | **Unit numbers** | U-01144 to U-01147 · four, from the unit series |
| 3 | **Address** | 412 Cypress Row, Silver Creek, TX 78611 |
| 4 | **Parcel** | R-114-0082-004 |
| 5 | **On the map** | 30.752104, −98.238391 · placed by the address lookup |
| 6 | **Checked against GIS** | Not checked yet |
| 7 | **Property type** | Apartment complex |
| 8 | **City limits** | Inside · city tax and the inside-city rate apply |
| 9 | **Area** | North Silver Creek |
| 10 | **Sub-area** | Cypress Row |
| 11 | **Read route** | Route 12 — North Silver Creek |
| 12 | **Billing cycle** | Cycle 3 — bills on the 12th |
| 13 | **Utility services** | Electric · Water · Sewer · Trash |
| 14 | **Owner** | Creekside Holdings LP |
| 15 | **Managed by** | Cane Island Property Co |
| 16 | **Units** | 4 — labelled 1, 2, 3, 4 · Residential |
| 17 | **Common areas** | Laundry · Corridor lighting · both bill to the owner |


**Rules it must obey**: A consequence preview before any commit that changes service state. Money at two decimals on screen and four in store. An absence is drawn as an absence and never as a zero.


---

## P4 · Property → Overview

`PRM-02` — Premises → a premise


**Header** — eyebrow `Premise` · title `412 Cypress Row`  
sub-line: P-00080 · Silver Creek, TX 78611 · Apartment complex · Active Route 12 · Cycle 3 — bills on the 12th


**Actions**, in this order: **✎ Edit** · **+ New unit** · **Change status** *(danger)*


**Tabs**: Overview | Units | Common areas | Assets | Work orders | Audit log


**Tiles** — every one carries a detail line:

| label | value | detail |
|---|---|---|
| Units | `4` | *3 occupied · 1 vacant* |
| Assets | `9` | *4 metered, all read this cycle* |
| Owed here | `$0.00` | *across 3 accounts* |
| Open work order | `1` | *meter change, Thursday* |


**Fact rows** — 13, ONE column, in this order:

| # | label | value as drawn |
|---|---|---|
| 1 | **Address** | 412 Cypress Row, Silver Creek, TX 78611 |
| 2 | **Parcel** | R-114-0082-004 |
| 3 | **On the map** | 30.752104, −98.238391 · placed by the address lookup, 8 Sep 2026 |
| 4 | **Checked against GIS** | Checked · D. Whitfield, 8 Sep 2026 |
| 5 | **City limits** | Inside |
| 6 | **Area** | North Silver Creek |
| 7 | **Sub-area** | Cypress Row |
| 8 | **Read route** | Route 12 — North Silver Creek · read on the 8th |
| 9 | **Billing cycle** | Cycle 3 · bills on the 12th |
| 10 | **Utility services** | Electric · Water · Sewer · Trash |
| 11 | **Owner** | Creekside Holdings LP · Landlord Master account A-10442 · Open it → |
| 12 | **Managed by** | Cane Island Property Co |
| 13 | **Common areas** | None on this property |


**Rules it must obey**: One page header. The danger tier for anything that takes a thing out of service. An absence is italic and grey and never a zero or an empty cell. Colour is never the only signal — every pill carries its word. A printed property number is shown; a database id never is.


---

## P5 · Property → Units

`PRM-02` — Premises → a premise → Units


**Header** — eyebrow `Premise` · title `412 Cypress Row`  
sub-line: P-00080 · Silver Creek, TX 78611 · Apartment complex · Active Route 12 · Cycle 3 — bills on the 12th


**Actions**, in this order: **✎ Edit** · **+ New unit** · **Change status** *(danger)* · **+ New unit**


**Tabs**: Overview | Units | Common areas | Assets | Work orders | Audit log


**Tiles** — every one carries a detail line:

| label | value | detail |
|---|---|---|
| Units | `4` | *3 occupied · 1 vacant* |
| Assets | `9` | *4 metered, all read this cycle* |
| Owed here | `$0.00` | *across 3 accounts* |
| Open work order | `1` | *meter change, Thursday* |


**Table columns**, in order: `Unit` · `Type` · `Floor` · `Meters` · `Occupant` · `Owed` · `Status` · *(no header — row actions, icons)*


**Footer**: Showing 4 of 4 · 3 occupied, 1 vacant ⇤ ← Page 1 of 1 → ⇥


**Rules it must obey**: A printed reference from the tenant's own series is shown; a database id never is. Money right-aligned, two decimals, tabular. An absence is drawn as an absence.


---

## P6 · Property → Common areas

`PRM-02` — Premises → a premise → Common areas


**Header** — eyebrow `Premise` · title `412 Cypress Row`  
sub-line: P-00080 · Silver Creek, TX 78611 · Apartment complex · Active Route 12 · Cycle 3 — bills on the 12th


**Actions**, in this order: **✎ Edit** · **+ New unit** · **Change status** *(danger)* · **+ Add a common area**


**Tabs**: Overview | Units | Common areas | Assets | Work orders | Audit log


**Tiles** — every one carries a detail line:

| label | value | detail |
|---|---|---|
| Units | `4` | *3 occupied · 1 vacant* |
| Assets | `9` | *4 metered, all read this cycle* |
| Owed here | `$0.00` | *across 3 accounts* |
| Open work order | `1` | *meter change, Thursday* |


**Fact rows** — 2, ONE column, in this order:

| # | label | value as drawn |
|---|---|---|
| 1 | **Laundry** | Shared room E · W Creekside Holdings LP A-10442 34.90 Active 👁 ✎ … |
| 2 | **Corridor lighting** | Shared lighting E Creekside Holdings LP A-10442 12.10 Active 👁 ✎ … |


**Table columns**, in order: `Common area` · `What it is` · `Meters` · `Billed to` · `Owed` · `Status` · *(no header — row actions, icons)*


**Footer**: Showing 2 of 2 · both bill to the owner's account ⇤ ← Page 1 of 1 → ⇥


**Rules it must obey**: Every list has an empty state that says what is missing and offers the action that fills it. No database id on screen.


---

## P7 · Property → Assets

`PRM-02` — Premises → a premise → Assets


**Header** — eyebrow `Premise` · title `412 Cypress Row`  
sub-line: P-00080 · Silver Creek, TX 78611 · Apartment complex · Active Route 12 · Cycle 3 — bills on the 12th


**Actions**, in this order: **✎ Edit** · **+ New unit** · **Change status** *(danger)*


**Tabs**: Overview | Units | Common areas | Assets | Work orders | Audit log


**Tiles** — every one carries a detail line:

| label | value | detail |
|---|---|---|
| Units | `4` | *3 occupied · 1 vacant* |
| Assets | `9` | *4 metered, all read this cycle* |
| Owed here | `$0.00` | *across 3 accounts* |
| Open work order | `1` | *meter change, Thursday* |


**Fact rows** — 9, ONE column, in this order:

| # | label | value as drawn |
|---|---|---|
| 1 | **MTR-40990** | Meter Water 2" the property itself 1 Jun 2026 28 Aug · 96 kgal Master 👁 ✎ … |
| 2 | **MTR-40218** | Sub-meter Electric Class 200 Unit 1 1 Jun 2026 28 Aug · 4,182 kWh In service 👁 ✎ … |
| 3 | **MTR-40219** | Sub-meter Water 5/8" Unit 1 1 Jun 2026 28 Aug · 14 kgal In service 👁 ✎ … |
| 4 | **MTR-40402** | Sub-meter Electric Class 200 Laundry 1 Jun 2026 28 Aug · 611 kWh In service 👁 ✎ … |
| 5 | **FIR-00311** | Fire service line Fire 6" the property itself 1 Jun 2026 not read — billed on size In service 👁 ✎ … |
| 6 | **CRT-08820** | Container / Cart Trash 96 gal Unit 1 1 Jun 2026 not read — billed per cart In service 👁 ✎ … |
| 7 | **ERT-51204** | Comms endpoint serves the water meter — Unit 1 1 Jun 2026 not read itself In service 👁 ✎ … |
| 8 | **BFP-00742** | Backflow preventer Water 2" the property itself 1 Jun 2026 not read — tested yearly Test due 30 Sep 👁 ✎ … |
| 9 | **PV-00119** | PV / solar Solar 7.2 kW Unit 4 14 Jul 2026 read through the net meter In service 👁 ✎ … |


**Table columns**, in order: `Asset ⇅` · `What it is` · `Service` · `Size` · `Where` · `Installed` · `Last read` · `Status` · *(no header — row actions, icons)*


**Footer**: Showing 9 of 9 · 4 read this cycle, 5 not read by design ⇤ ← Page 1 of 1 → ⇥


**Rules it must obey**: Consumption always carries its unit. An absence is drawn as an absence and says why. Colour is never the only signal. Row actions are icons with tooltips.


---

## P8 · Property → Work orders

`PRM-02` — Premises → a premise → Work orders


**Header** — eyebrow `Premise` · title `412 Cypress Row`  
sub-line: P-00080 · Silver Creek, TX 78611 · Apartment complex · Active Route 12 · Cycle 3 — bills on the 12th


**Actions**, in this order: **✎ Edit** · **+ New unit** · **Change status** *(danger)* · **⚡ Raise work here**


**Tabs**: Overview | Units | Common areas | Assets | Work orders | Audit log


**Tiles** — every one carries a detail line:

| label | value | detail |
|---|---|---|
| Units | `4` | *3 occupied · 1 vacant* |
| Assets | `9` | *4 metered, all read this cycle* |
| Owed here | `$0.00` | *across 3 accounts* |
| Open work order | `1` | *meter change, Thursday* |


**Fact rows** — 2, ONE column, in this order:

| # | label | value as drawn |
|---|---|---|
| 1 | **WO-4822** | Meter change Unit 4 K. Osei Thu 11 Sep, am Scheduled 👁 … |
| 2 | **WO-4610** | Leak investigation Laundry — Not booked yet Waiting 👁 … |


**Table columns**, in order: `Work` · `What` · `Where` · `Crew` · `Booked` · `Status` · *(no header — row actions, icons)*


**Footer**: Showing 2 open · 7 done in the last year ⇤ ← Page 1 of 1 → ⇥


**Rules it must obey**: An absence is drawn as an absence. Row actions are icons with tooltips. Button grammar: ⚡ raises work.


---

## P9 · Property → Audit log

`PRM-02` — Premises → a premise → Audit log


**Header** — eyebrow `Premise` · title `412 Cypress Row`  
sub-line: P-00080 · Silver Creek, TX 78611 · Apartment complex · Active Route 12 · Cycle 3 — bills on the 12th


**Actions**, in this order: **✎ Edit** · **+ New unit** · **Change status** *(danger)*


**Tabs**: Overview | Units | Common areas | Assets | Work orders | Audit log


**Tiles** — every one carries a detail line:

| label | value | detail |
|---|---|---|
| Units | `4` | *3 occupied · 1 vacant* |
| Assets | `9` | *4 metered, all read this cycle* |
| Owed here | `$0.00` | *across 3 accounts* |
| Open work order | `1` | *meter change, Thursday* |


**Table columns**, in order: `When` · `Who` · `What changed` · `From` · `To` · *(no header — row actions, icons)*


**Footer**: Showing 4 of 4 ⇤ ← Page 1 of 1 → ⇥


**Rules it must obey**: Every money or service action is recorded with who, when and what. No database id on screen. An absence is drawn as an absence.


---

## P10 · Edit a property

`PRM-02` — Premises → a premise → Edit


**Header** — eyebrow `Premise` · title `Edit this premise`  
sub-line: Changes take effect at once. Everything is recorded.


**Actions**, in this order: **Cancel** · **✎ Change these** · **Change** · **Cancel** · **Save changes ✓** *(primary)*


**Rules it must obey**: A consequence preview before any commit that changes service state, and an address is exactly that. Required asterisks only where the server insists. A multiple choice is chips plus an add control.


---

## P11 · Take a property out of service

`PRM-02 · PRM-03` — Premises → a premise → Change status · Premises → Units → a unit → Change status


**Header** — eyebrow `Premise` · title `Change status`  
sub-line: Currently Active.


**Actions**, in this order: **Cancel** · **Cancel** · **Deactivate premise** *(danger)*


**Rules it must obey**: The danger tier for destructive commits. A refusal caps at five or six words. A consequence preview before the commit. Every money-or-service action is recorded with who, when and what.


---

## U1 · The units list

`S15 · PRM-01U` — Premises → Units


**Header** — eyebrow `Premises & Units` · title `Units`  
sub-line: Every unit that can take service, across every property.


**Actions**, in this order: **↑ Import** · **+ New unit** *(primary)*


**Tabs**: Premises | Units | Imports


**Table columns**, in order: `Unit ⇅` · `Address ⇅` · `Type` · `Services` · `Meters` · `Occupant` · `Owed` · `Status` · *(no header — row actions, icons)*


**Footer**: Showing 1–50 of 1,109 · Rows per page 50 ⇤ ← Page 1 of 23 → ⇥


**Rules it must obey**: A printed reference from the tenant's own series is shown; a database id never is. Money right-aligned, two decimals, tabular. A pagination footer on every list. Search placeholders name what is searched.


---

## U2 · Add units · Details

`S16 · PRM-07` — Premises → + New unit → step 1 · from a property, or from the units list


**Header** — eyebrow `Units` · title `Add units`  
sub-line: A unit always belongs to a building. Start by saying which.


**Actions**, in this order: **Cancel** · **Change** · **Cancel** · **Continue →** *(primary)*


**Rules it must obey**: A consequence preview before the commit. A refusal is short and says what to do, not what went wrong. Button grammar: a tick commits.


---

## U3 · Add units · Review & create

`S16 · PRM-07` — Premises → + New unit → step 2


**Header** — eyebrow `Units` · title `Review & create`  
sub-line: Everything you have entered. Nothing is written until you press Create.


**Actions**, in this order: **Cancel** · **← Back** · **Create 3 units ✓** *(primary)*


**Fact rows** — 13, ONE column, in this order:

| # | label | value as drawn |
|---|---|---|
| 1 | **Building** | 412 Cypress Row · P-00080 · Silver Creek, TX 78611 · Apartment complex |
| 2 | **It has today** | 1 unit, numbered 1 |
| 3 | **Route and cycle** | Route 12 · Cycle 3 — every unit made here inherits both |
| 4 | **Services** | Electric · Water · Sewer · Trash — from the building |
| 5 | **How many** | 3, numbered from 2 |
| 6 | **Unit numbers** | U-01145 to U-01147 · three, from this utility's unit series |
| 7 | **Unit type** | Residential |
| 8 | **Floor** | Not recorded |
| 9 | **Plan** | Residential Standard · from the day each unit is created |
| 10 | **Common areas** | None being added here |
| 11 | **2** | U-01145 Residential Residential Standard Vacant, no meter |
| 12 | **3** | U-01146 Residential Residential Standard Vacant, no meter |
| 13 | **4** | U-01147 Residential Residential Standard Vacant, no meter |


**Table columns**, in order: `Label` · `Unit number` · `Type` · `Plan` · `Starts`


**Rules it must obey**: A consequence preview before the commit. Button grammar: an arrow navigates, a tick commits. An absence is drawn as an absence. A refusal is short and says what to do. Every money-or-service action is recorded with who, when and what.


---

## U4 · Unit → Overview

`S15 · PRM-03` — Premises → Units → a unit


**Header** — eyebrow `Unit` · title `Unit 2`  
sub-line: U-01145 · 412 Cypress Row, Silver Creek, TX 78611 · Residential · Active Occupied Route 12 · Cycle 3 — from the building


**Actions**, in this order: **✎ Edit** · **Move** · **Change status** *(danger)*


**Tabs**: Overview | Assets | Plan | Account | Occupancy | Audit log


**Tiles** — every one carries a detail line:

| label | value | detail |
|---|---|---|
| Assets | `5` | *2 metered · 3 behind the meter* |
| Owed | `$61.40` | *due 24 Sep* |
| Plan | `Standard` | *since 1 Jun 2026* |
| Open work | `—` | *nothing booked* |


**Fact rows** — 8, ONE column, in this order:

| # | label | value as drawn |
|---|---|---|
| 1 | **In this building** | 412 Cypress Row, Silver Creek, TX 78611 Apartment complex · 4 units · Open it → |
| 2 | **Floor** | Not recorded |
| 3 | **Floor area** | Not recorded |
| 4 | **Parcel** | R-114-0082-004 · from the building |
| 5 | **On the map** | 30.752104, −98.238391 · from the building Give this unit its own point |
| 6 | **Checked against GIS** | Checked · inherited with the building's point |
| 7 | **Account** | A-10517 · M. Alvarez · Active · since 1 Jun 2026 · Residential Owes $61.40 , due 24 Sep · deposit $150.00 held · autopay on Open the account → |
| 8 | **Services** | Electric · Water |


**Rules it must obey**: An absence is italic and grey and never a zero. Consumption always carries its unit. A unit label a clerk reads down the phone is shown; a database id never is. The danger tier for taking a thing out of service.


---

## U5 · Unit → Assets

`S15 · PRM-03` — Premises → Units → a unit → Assets → + Assign from inventory


**Header** — eyebrow `Unit` · title `Unit 2`  
sub-line: U-01145 · 412 Cypress Row, Silver Creek, TX 78611 · Residential · Active Occupied Route 12 · Cycle 3 — from the building


**Actions**, in this order: **✎ Edit** · **Move** · **Change status** *(danger)* · **+ Assign from inventory** · **Assign ✓** *(primary)* · **Assign ✓** · **Assign ✓**


**Tabs**: Overview | Assets | Plan | Account | Occupancy | Audit log


**Tiles** — every one carries a detail line:

| label | value | detail |
|---|---|---|
| Assets | `5` | *2 metered · 3 behind the meter* |
| Owed | `$61.40` | *due 24 Sep* |
| Plan | `Standard` | *since 1 Jun 2026* |
| Open work | `—` | *nothing booked* |


**Fact rows** — 5, ONE column, in this order:

| # | label | value as drawn |
|---|---|---|
| 1 | **MTR-40218** | Electric Class 200 In service 1 Jun 2026 28 Aug · 4,182 kWh ✎ − … |
| 2 | **MTR-40219** | Water 5/8" In service 1 Jun 2026 28 Aug · 14 kgal ✎ − … |
| 3 | **MTR-41007** | Water 5/8" Main depot · shelf B In stock Assign ✓ |
| 4 | **MTR-41008** | Water 5/8" Van 3 · K. Osei Held by a technician Assign ✓ |
| 5 | **MTR-40990** | Water 1" Main depot · shelf B In stock Assign ✓ |


**Table columns**, in order: `Meter` · `Service` · `Size` · `Status` · `On since` · `Last read` · *(no header — row actions, icons)* · `Meter` · `Service` · `Size` · `Where it is` · `Status` · *(no header — row actions, icons)*


**Footer**: Showing 3 of 3 in stock · 41 water meters in inventory Assigning records the start read and takes it out of stock.


**Rules it must obey**: Row actions are icons with tooltips. A refusal caps at five or six words and says what to do. A consequence preview before a commit that changes service state. Colour is never the only signal.


---

## U6 · Unit → Plan

`S15 · PRM-03` — Premises → Units → a unit → Plan


**Header** — eyebrow `Unit · 101 Silver Creek Rd` · title `Unit 1`  
sub-line: SCW-U-001 · Ottumwa, IA · Residential · Active Occupied Water · Sewer · Trash · Solar · Battery · Fire — the six this unit can take


**Actions**, in this order: **✎ Edit** · **Move** · **Change status** *(danger)* · **Change plan →**


**Tabs**: Overview | Assets | Plan | Account | Occupancy | Audit log


**Tiles** — every one carries a detail line:

| label | value | detail |
|---|---|---|
| Assets | `5` | *2 metered · 3 behind the meter* |
| Owed | `$61.40` | *due 24 Sep* |
| Plan | `Standard` | *since 1 Jun 2026* |
| Open work | `—` | *nothing booked* |


**Fact rows** — 14, ONE column, in this order:

| # | label | value as drawn |
|---|---|---|
| 1 | **Current plan** | Sample — Residential · version 1 · published |
| 2 | **Plan code** | SCW-RES |
| 3 | **Effective from** | 1 Jun 2026 |
| 4 | **Base charges** | $22.00 a month · the six service base charges below add to this |
| 5 | **Minimum bill** | No floor is set — a bill can be any amount, including nothing |
| 6 | **Locked to this unit** | No · a change here does not need a supervisor |
| 7 | **Vacant standby** | No · nothing bills while the unit is empty |
| 8 | **Eligibility** | Not checked — no plan on this system asks for proof yet |
| 9 | **Water** | 8.00 Inclining tiers · Sample — Residential water none |
| 10 | **Sewer** | 9.00 A percentage of water · Sample — Sewer none |
| 11 | **Trash** | 0.00 Per cart, monthly — not measured · Sample — Trash none |
| 12 | **Solar** | 0.00 By capacity · Sample — Solar capacity none |
| 13 | **Battery** | 5.00 By capacity · Sample — Battery capacity none |
| 14 | **Fire** | 0.00 By the size of the line, times how many · Sample — Fire capacity none |


**Table columns**, in order: `Service` · `Base a month` · `Priced on` · `Minimum`


**Rules it must obey**: Money two decimals on screen, four in store. A consequence preview before a commit that changes service state. An absence is drawn as an absence. No rule id or internal code in clerk-facing copy. A description budget of one sentence per section.


---

## U7 · Unit → Account

`S15 · PRM-03` — Premises → Units → a unit → Account


**Header** — eyebrow `Unit` · title `Unit 2`  
sub-line: U-01145 · 412 Cypress Row, Silver Creek, TX 78611 · Residential · Active Occupied Route 12 · Cycle 3 — from the building


**Actions**, in this order: **✎ Edit** · **Move** · **Change status** *(danger)* · **Open the account →** · **Move-out…** *(danger)*


**Tabs**: Overview | Assets | Plan | Account | Occupancy | Audit log


**Tiles** — every one carries a detail line:

| label | value | detail |
|---|---|---|
| Assets | `5` | *2 metered · 3 behind the meter* |
| Owed | `$61.40` | *due 24 Sep* |
| Plan | `Standard` | *since 1 Jun 2026* |
| Open work | `—` | *nothing booked* |


**Fact rows** — 20, ONE column, in this order:

| # | label | value as drawn |
|---|---|---|
| 1 | **Account** | A-10517 · M. Alvarez · customer C-04412 |
| 2 | **Status** | Active · opened 1 Jun 2026 |
| 3 | **Class** | Residential · this decides which base charge the plan applies |
| 4 | **Reach them by** | Nothing recorded — no paperless choice, no SMS, no language |
| 5 | **Post** | 412 Cypress Row, Silver Creek, TX 78611 · the building's address; no separate billing address |
| 6 | **In the old system** | No reference recorded |
| 7 | **Owed** | 61.40 · due 24 Sep 2026 · not yet overdue |
| 8 | **Last bill** | 28 Aug 2026 · 61.40 · BL-2608-000052 |
| 9 | **Last payment** | 2 Aug 2026 · 58.10 · card, cleared |
| 10 | **Deposit held** | 150.00 · taken 1 Jun 2026 · returns on close, against what is owed |
| 11 | **Autopay** | On · and the account is not cash-only, so it will be taken |
| 12 | **Payment plan** | None running |
| 13 | **Budget billing** | Not enrolled |
| 14 | **Collections** | Not in collections |
| 15 | **Payments that bounced** | 0 |
| 16 | **Tax exemption** | None claimed |
| 17 | **Previous account** | R. Nakamura · A-10388 · 3 Feb 2024 to 28 May 2026 · closed, nothing outstanding |
| 18 | **Vacant between** | 28 May to 1 Jun 2026 · 4 days, base charges billed to the owner |
| 19 | **📌 Medical protection** | Certificate received 4 Aug 2026, renews 31 Mar 2027. D. Whitfield · not visible to the customer |
| 20 | **Meter access** | Dog in the side yard — ring first. A. Reyes, 12 Jun 2026 · visible to the customer |


**Rules it must obey**: Money two decimals on screen, four in store. Colour is never the only signal. An absence is drawn as an absence. The danger tier for anything that ends service. No database id on screen — an account number and a customer number are printed references.


---

## U8 · Unit → Occupancy

`S15 · PRM-03` — Premises → Units → a unit → Occupancy


**Header** — eyebrow `Unit` · title `Unit 2`  
sub-line: U-01145 · 412 Cypress Row, Silver Creek, TX 78611 · Residential · Active Occupied Route 12 · Cycle 3 — from the building


**Actions**, in this order: **✎ Edit** · **Move** · **Change status** *(danger)*


**Tabs**: Overview | Assets | Plan | Account | Occupancy | Audit log


**Tiles** — every one carries a detail line:

| label | value | detail |
|---|---|---|
| Assets | `5` | *2 metered · 3 behind the meter* |
| Owed | `$61.40` | *due 24 Sep* |
| Plan | `Standard` | *since 1 Jun 2026* |
| Open work | `—` | *nothing booked* |


**Fact rows** — 1, ONE column, in this order:

| # | label | value as drawn |
|---|---|---|
| 1 | **M. Alvarez** | A-10517 1 Jun 2026 still here 61.40 Current |


**Table columns**, in order: `Occupant` · `Account` · `From` · `To` · `Left owing` · `Status`


**Footer**: Showing 3 · this unit has been vacant once in two years ⇤ ← Page 1 of 1 → ⇥


**Rules it must obey**: An absence is drawn as an absence, never an empty cell. Money right-aligned and tabular. No database id on screen.


---

## U9 · Unit → Audit log

`S15 · PRM-03` — Premises → Units → a unit → Audit log


**Header** — eyebrow `Unit` · title `Unit 2`  
sub-line: U-01145 · 412 Cypress Row, Silver Creek, TX 78611 · Residential · Active Occupied Route 12 · Cycle 3 — from the building


**Actions**, in this order: **✎ Edit** · **Move** · **Change status** *(danger)*


**Tabs**: Overview | Assets | Plan | Account | Occupancy | Audit log


**Tiles** — every one carries a detail line:

| label | value | detail |
|---|---|---|
| Assets | `5` | *2 metered · 3 behind the meter* |
| Owed | `$61.40` | *due 24 Sep* |
| Plan | `Standard` | *since 1 Jun 2026* |
| Open work | `—` | *nothing booked* |


**Table columns**, in order: `When` · `Who` · `What changed` · `From` · `To`


**Footer**: Showing 3 of 3 ⇤ ← Page 1 of 1 → ⇥


**Rules it must obey**: Every money or service action is recorded with who, when and what. No database id on screen.


---

## U10 · Edit a unit

`S15 · PRM-03` — Premises → Units → a unit → Edit


**Header** — eyebrow `Unit` · title `Edit Unit 2`  
sub-line: U-01145 · 412 Cypress Row, Silver Creek, TX 78611 · Residential · Active Occupied Route 12 · Cycle 3 — from the building


**Actions**, in this order: **Cancel** · **Give this unit its own** · **Cancel** · **Save changes ✓** *(primary)*


**Rules it must obey**: Required asterisks only where the server insists. A refusal caps at five or six words and says what to do. A multiple choice is chips plus an add control.


---

## U11 · Move a unit to another property

`S15 · PRM-03` — Premises → Units → a unit → Move


**Header** — eyebrow `Unit` · title `Move Unit 1 to another property`  
sub-line: SCW-U-001 · Residential · Active Occupied


**Actions**, in this order: **Cancel** · **Cancel** · **Move unit ✓** *(danger)*


**Fact rows** — 7, ONE column, in this order:

| # | label | value as drawn |
|---|---|---|
| 1 | **Bills already issued** | Stay on 101 Silver Creek Rd . Nothing already billed moves. |
| 2 | **The next bill** | Is attributed to the new property, from 8 Sep 2026. |
| 3 | **Accounts this unit has carried** | 2 — a report that reads a unit's current property will show both under the new one. |
| 4 | **Bills it has produced** | Cannot be counted — nothing counts bills for a single unit yet |
| 5 | **Route and cycle** | Route 12 · Cycle 3 → Route 4 · Cycle 1 , from the new building. |
| 6 | **Meters and assets** | The 5 tagged to this unit travel with it. Their addresses are the building's, so all five change address too. |
| 7 | **Recorded** | Both properties, the date and your reason, in the audit log. |


**Rules it must obey**: The danger tier for a commit that cannot be simply undone. A consequence preview before the commit. A refusal caps at five or six words. Every service action is recorded with who, when and what. An absence is drawn as an absence.


---

## U12 · Take a unit out of service

`S15 · PRM-03` — Premises → Units → a unit → Change status


**Header** — eyebrow `Unit` · title `Change status`  
sub-line: Unit 2 · 412 Cypress Row · currently Active


**Actions**, in this order: **Cancel** · **Cancel** · **Deactivate unit** *(danger)*


**Rules it must obey**: The danger tier for destructive commits. A refusal caps at five or six words. Every service action is recorded with who, when and what.
