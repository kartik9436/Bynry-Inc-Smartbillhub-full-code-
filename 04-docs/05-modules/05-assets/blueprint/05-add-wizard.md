# § 06 · Adding an asset — screens 28–33 measured against the code

**What this is.** A drawing-versus-code diff of the six screens in section 06 of
`05-prototype/01 Assets Menu Blueprint.pdf` (pages 108–124). It measures and routes.
**It builds nothing and changes no product code.**

**How it was made — B14 rule 42.** Every page was rendered to PNG with
`10-scripts/pdf/pdf_render.py` and **opened as an image**. Pages 108 and 110–125 at
scale 2 (1584×1224); **page 109 at scale 4 (3168×2448)**, because its ten-row table is
the densest thing in the section. PO 2026-09-13: *"When you use images to create screens
your accuracy is higher; hence dont create screens using only Text"*.

> ⚠ **NO LAYOUT, FIELD, LABEL, COLUMN OR ORDERING IN THIS FILE CAME FROM A DERIVED
> COPY.** `wireframes/CR-092-assets-screens.html` and `08-screen-layouts.md` are second
> copies of the wireframes and are free to drift (hard-won law 5). Neither was opened
> for layout. `08-screen-layouts.md` was read for **one** thing — the factual record of
> what has already been built and in which version — and that is history, not
> specification. **Nothing in this file needed correcting as a result**, because nothing
> in it was ever taken from either.

**Versions.** The document was read at `2.234.17` (commit `79c659d7`, 2026-09-10/11).
The product is at **`2.261.3`** today (`07-frontend/package.json:4`). Page 2 of the
blueprint says the staleness covers descriptions, field tables, routes, measured
figures and drawings of a screen as it is — **not rulings**. So every as-built claim
below was re-checked against the code, and the ones that have since been fixed are
marked.

**B14.** Counted from B14's own status table, not from a pointer: **33 binding rules**,
numbered **1–21 and 31–42** (rows 1–20 and 32, 34–42 at
`04-docs/02-decisions/14-ui-conventions.md:35–64`; rows 21, 31 and 33 at lines 228–230).
22–29 were never minted; 30 was declined.

**Rule 38 governs this file.** *"if youa re doing a form - go as per our UI rules"* —
where the drawing and our UI rules disagree about **how a form is built** (fields side
by side, helper position, footer button order, row-action style), the UI rules win and
the divergence is recorded here rather than built. What the form **contains** is still
the drawing's to decide. Rule 37 also governs: `AST-04415`, `S-2004`, `41-8827944`,
`$182.00`, `09/11/2026`, `4 waiting`, `3 days` and every other inked figure is an
**illustration**. None is asserted below and none may be seeded into a fixture.

---

## The section head — page 108

> **06 · Adding an asset — the four steps and the commit**
>
> *"One address, `/:tenant/assets/new?class=`, four steps and a final ✓ — and it is a
> **page**, not a dialog, because it creates something. The wizard branches on **three
> classes**, so what you are asked for on steps 1 and 2 depends on what you are adding."*

Both halves hold in the code. `App.tsx:1069` mounts `<AssetAddWizard />` at
`assets/new` as a full page; `assetsShared.tsx:89` declares exactly three classes
(`meters`, `sub_meters`, `behind_the_meter`) and `AssetAddWizard.tsx:562
switchClass()` restarts the flow on a class change.

⚠ **The head says "four steps and the commit" and every figure in the section draws a
FIVE-box step rail** — `1 Identity › 2 Specification › 3 Assignment › 4 Lifecycle ›
5 Review`. The code declares **four** (`ADD_STEP_COUNT = 4`,
`AssetAddWizard.tsx:113`), and the commit rides on step 4. That single fact is screen
32 and is the largest gap in the section.

---

## THE TABLE ON PAGE 109 — reproduced exactly off the image

> ### Ten columns an asset can hold are never asked for here — and seven of them are never asked for anywhere
>
> The wizard captures **26** of the asset's usable columns. These are the ones it does
> not, checked against the model:
>
> | Not captured at Add | Capturable anywhere else? |
> |---|---|
> | **External reference** | **No.** Served on every row, rendered nowhere, typed nowhere. It can only arrive by import |
> | **Form / class** | **No.** Zero capture sites in the front end |
> | **Seal #** | **No.** Zero capture sites — and a seal is fitted *at installation*, which is this screen |
> | **Location note** | **No.** Zero capture sites — where a technician will actually find it |
> | **Depreciation method** | **No.** The present value is computed from it and nobody can set it |
> | **Allocation share** ⚠ | **No. Sub-meter only**, and this is the sharpest of them: a sub-meter created here is *metered, not allocated*, and there is no screen that can ever allocate it |
> | **Allocation rule** ⚠ | **No.** Same |
> | **Loss tolerance** ⚠ | **No.** Same |
> | Opening read | Refused, with a sentence — `AST-B-14` reopened it |
> | Last test date | **Yes** — a *test* entry on Log repair sets it. Not a gap |
>
> ⚠ **Seven of the ten have no capture site anywhere in the front end.** They can be
> displayed and can never be entered — which is **hard-won law 2 in a third form**: not
> a dead control, not a stale refusal, but a **column with a reader and no writer**.
> Specification `AST-B-27`. Each is marked **NEW** on the step it belongs to below, and
> the three allocation rows appear on the **sub-meter** variant only.

### My verification of every row, against the code at 2.261.3

**The headline: the "seven with no capture site anywhere" is now ZERO. All ten have a
writer.** Three of them acquired one *at Add* and four more acquired one on the asset's
own edit dialogs. Every claim below is a file and a line I read.

The edit dialogs are reachable: `AssetPanelEditDialog` is mounted at
`AssetDetailPage.tsx:634`, its panel set is `ASSET_OVERVIEW_PANELS` at
`AssetDetailPage.tsx:689` (`assignment · due · measurement · device · cost · lifecycle`),
and each panel opens from the pencil on the panel it names. This is checked in the
direction hard-won law 2 asks for — the control is passed, not merely declared.

| Column | Model | Accepted by `POST /assets` | Capture site TODAY | Doc's answer | Verdict |
|---|---|---|---|---|---|
| External reference (`external_ref`) | `apps/assets/models.py:256` | yes — `services.py:646` | `AssetPanelEdits.tsx:650` (`EditDevice`, line 543) | No | **WRONG NOW** — fixed since 2.234.17. Still **not on the wizard** |
| Form / class (`form_class`) | `models.py:335` | yes — `services.py:670` | `AssetPanelEdits.tsx:657` (`EditDevice`) | No | **WRONG NOW.** Still not on the wizard |
| Seal # (`seal_no`) | `models.py:338` | yes — `services.py:673` | `AssetPanelEdits.tsx:669` (`EditDevice`) | No | **WRONG NOW.** Still not on the wizard — and the drawing's own point stands: a seal is fitted at installation, which is this screen |
| Location note (`location_note`) | `models.py:343` | yes — `services.py:677` | `AssetPanelEdits.tsx:839` (`EditLifecycle`, line 795) | No | **WRONG NOW.** Still not on the wizard |
| Depreciation method (`depreciation_method`) | `models.py:354` | yes — `services.py:688` | `AssetPanelEdits.tsx:757` (`EditCostValue`, line 690) | No | **WRONG NOW.** Still not on the wizard |
| Allocation share (`allocation_share_pct`) | `models.py:368` | yes — `services.py:692` | **`AssetAddWizard.tsx:1155`** (step 2, sub-meters) + `AssetPanelEdits.tsx:483` | No | **FIXED AT ADD** — `AST-B-27`, PO 2026-09-12 |
| Allocation rule (`allocation_rule`) | `models.py:372` | yes — `services.py:678` | **`AssetAddWizard.tsx:1163`** (step 2, a chooser over `ALLOCATION_RULES`) + `AssetPanelEdits.tsx:491` | No | **FIXED AT ADD** |
| Loss tolerance (`loss_tolerance_pct`) | `models.py:373` | yes — `services.py:679` | `AssetPanelEdits.tsx:503` (`EditMeasurement`, line 284) | No | **WRONG NOW.** Still not on the wizard |
| Opening read | **not a column** — written to `meter_reads` inside the create's transaction (`apps/assets/services.py:1026 _capture_opening_read`) | yes — `services.py:708–709` | **`AssetAddWizard.tsx:1200`** + its read date at `:1208` | Refused, `AST-B-14` reopened it | **FIXED** — the refusal was deleted from step 3, not un-disabled |
| Last test date (`last_test_date`) | `models.py:340` | yes — `services.py:675` | a `test` entry on Log repair | Yes | **CORRECT, unchanged** |

**The arithmetic moved and here is the whole of it.** `AddWizardValues`
(`AssetAddWizard.tsx:128–212`) holds **33 keys** today against the **29** the document
measured. The four added are `opening_read`, `opening_read_date`,
`allocation_share_pct` and `allocation_rule`. Two of the four are asset columns, so the
wizard now captures **28 asset columns, not 26**, and the "ten not captured at Add" is
**seven**.

⚠ **`AST-B-27`'s own premise still holds for the remaining seven, and it is worth
saying plainly: they are capturable, but only on a screen you reach AFTER the asset
exists.** A seal fitted during installation, a location note the installer is standing
in, an external reference while the paperwork is in hand — all three are facts a person
holds at Add and must now come back for. That is the specification's argument and the
code has not answered it.

---

## Screen 28 · Add an asset · 1 Identity — pages 109–112

`/:tenant/assets/new?class=meters` · chips **EXISTS BEHIND · NEW BUILD** ·
commitments 03, 26, 27, 28 · figure 43 (meter), figure 44 (sub-meter)

### What the drawing shows

**Lede:** *"What is this thing, and what will we call it?"*

**Page frame** (identical on all five figures): back link **← Assets** · kicker
**`METER · ADD AN ASSET`** (the class, then the flow) · title **`AST-04415`** · a
**`New`** chip beneath it · sub-line *"Not created yet · the number is reserved when
you finish"* · a **`…`** overflow at the far right · the version stamp and the signed-in
user bottom-left.

**Step rail:** five boxes — `1 Identity` (active) `› 2 Specification › 3 Assignment ›
4 Lifecycle › 5 Review`.

**Fields, in drawn order (meter, fig 43):**

1. **Asset class \*** — a three-option segmented control on its own **full-width** row:
   `Meter · Sub-meter · Behind-the-meter device`. Annotated `FIX · 3 · BR-AST-004`.
2. **Asset number \*** (left) — helper *"The next number in the tenant's series."*
   **Asset type \*** (right, annotated `SET · ASSET_TYPES`) — helper *"The catalogue
   entry for this kind."*
3. **Utility service** with an amber **`affects billing`** badge and `*`, annotated
   `SET · SETTINGS/SERVICES` (left) — a dropdown reading `Water`, helper *"One of the
   tenant's enabled services."* **NEW**
   **Device ID / serial** (right) — helper *"The manufacturer's number, not ours."*
4. **External reference** (left, half width) — helper *"Your own or a third party's
   number."* **NEW**

**Closing note, in small type:** *"The service is asked HERE and not on the
specification step, because it decides what that step offers. `offersConnectionSize()`:
a meter always gets a connection size, a sub-meter never, and a behind-the-meter device
only once a service is entered."*

**Footer, right-aligned:** `Save as draft` **NEW** · `Continue`.

**Sub-meter variant (fig 44):** the class chooser lands on the second option and the
rows re-shape — row 1 `Asset number *` | **`Parent master *`** (annotated
`TBL · ASSETS · METERS TAB`, *"Search meters…"*, helper *"A sub-meter cannot exist
without one."*); row 2 `Asset type *` | `Utility service *`; row 3 `Device ID / serial`
alone. **External reference is not drawn on this variant.** Footer identical.

**The document corrects itself on this page (p111):** *"This document's first drawing of
step 1 left it out, which was an omission on my part"* — the utility service. The later
statement is the one used above.

**"The screen" table (p112):** For — *whoever is booking in a new device* · How you get
here — *`+ Add asset` on any registry tab* · Primary action — *`Continue`. Nothing is
created until step 5* · Tabs — *None — a five-step rail* · Write surfaces — *Add, and
only at the end. Edit · Update · Delete — **NOTHING*** · Spacing — *class on its own
full-width row, then two to a row* · Health — **SERVED** for every field, *two are NEW
here*.

### What the code does today

`07-frontend/src/features/assets/AssetAddWizard.tsx`, `IdentityStep` at **line 953**.

| | Code |
|---|---|
| Page frame | `PageHeader` at `:882` — `backTo` **← Assets** ✓, kicker **"Assets"**, title **"Add an asset"**. **No chip, no sub-line, no `…` overflow.** |
| Step rail | `steps` at `:731`, four entries: Identity · Specification · Assignment · Lifecycle. `WizardFrame.tsx:795` draws them |
| Lede | `:975` — *"The asset number is how field crews and imports will find it. It has to be unique."* |
| Asset class | `SegmentedField` `:977`, options from `ASSET_TAB_IDS` — three ✓, full width ✓ |
| Asset number | `TextField` `:984`, **full width**, **not `required`**, helper *"Leave blank to take the next number from your series, with this type's prefix. Duplicates are rejected."* |
| Availability | a `Note` at `:998` — *"Next in the series: …"* / taken. **Not drawn anywhere** |
| Asset type · Read method | a **2-column grid** at `:1004` — `type` `:1006` (`required` ✓, **no helper**) and **`read_method`** `:1015` |
| Utility service | `SelectField` `:1040`, full width, `required={requiresService(klass)}`, options from `GET /settings/services`, helper *"One of your utility's enabled services."* **No `affects billing` badge** |
| Parent master | `SearchSelectField` `:1049`, sub-meters only, **last**, full width, `required` ✓ |
| Device ID / serial | **not on this step** — `serial_no` is on step 2 (`:1237` measuring, `:1387` device) |
| External reference | **absent from the whole wizard** |
| Closing note | absent |
| Footer | `WizardFrame.tsx:851–884` — `Save & exit` · a **disabled `Park`** carrying *"Drafts are not kept yet."* · `Back` (step > 1) · `Continue` |

### Gaps — screen 28

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| Utility service is a picker | a dropdown over the tenant's enabled services | `SelectField` fed by `GET /settings/services` (`AssetAddWizard.tsx:640, 1040`) | — | **YES — `AST-B-03` is BUILT** (`DEF-MET-4980/4981`). The document's "today it is a plain text box" is stale |
| `GET /settings/services` permission | `AnyTenantRole`, so every staff role can read it | true — `apps/tenancy/api.py:417` `@permission_classes([AnyTenantRole])`, route registered at `:1105` | — | **YES** — the document already corrected itself here and the correction is right |
| External reference | a field on step 1, marked **NEW** | absent from the wizard; capturable only on the asset's Device edit dialog (`AssetPanelEdits.tsx:650`) | CONTENT | No. `POST /assets` already accepts `external_ref` (`services.py:646`) — **no plumbing needed** |
| Read method's step | step **2**, beside Connection size | step **1**, beside Asset type (`:1015`) | LAYOUT | No |
| Device ID / serial's step | step **1**, beside Utility service | step **2** (`:1237` / `:1387`) | LAYOUT | No |
| Asset number's row | two to a row with Asset type | full width on its own row (`:984`) | LAYOUT | No |
| Asset number label | `Asset number` | `Asset #` (`assets.form.assetNo`) | CONTENT | No |
| Asset number required marker | drawn with `*` | not `required`; `stepValid(1)` (`:295`) permits blank, which takes the next in series | CONTENT — **conflict, not a defect** | No. The code's behaviour is `BR-AST-026`'s series suggestion and the helper says so. **The drawing's asterisk is the thing to question, not the code** |
| Asset type helper | *"The catalogue entry for this kind."* | no helper | CONTENT | No |
| `affects billing` badge | drawn on Utility service | no badge anywhere in the wizard | CONTENT | No |
| Sub-meter field order | `Asset number \| Parent master` then `Asset type \| Utility service` then `Device ID` | Asset number, then `Asset type \| Read method`, then Utility service, then Parent master **last** | LAYOUT | No |
| Page head: title, chip, sub-line, `…` | title is the reserved number, a `New` chip, *"Not created yet · the number is reserved when you finish"*, an overflow menu | kicker "Assets", title "Add an asset", none of the other three (`:882`) | LAYOUT + CONTENT (4 elements) | No |
| Step rail length | five boxes | four (`ADD_STEP_COUNT = 4`, `:113`) | LAYOUT — and it is screen 32 | No |
| Footer | one exit, `Save as draft` | `Save & exit` + a disabled `Park` refusing over *"Drafts are not kept yet."* | CONTENT + **MISSING PLUMBING** | No — see screen 33 |
| Availability note | not drawn | a `Note` the drawing does not have (`:998`) | CONTENT — **code has more than the drawing** | n/a |

**Rule 33 breaches on this step** (LABEL ≤ 3 words · FACT ≤ 6 · INSTRUCTION ≤ 6 per
sentence): the asset-number helper is a 16-word first sentence; the serial helper
(`assets.form.serialHelp`) is 8 + 12. The drawing's replacements are 6 and 5 words and
are compliant — **the drawing is the better copy here and B14 agrees with it.**

**A drawing inconsistency to record rather than resolve:** fig 43 draws External
reference and fig 44 does not. Both are frames of one screen, so the *frame wins*
ruling cannot settle it. Under rule 37 the shape both agree on is built and the
difference is a question — **is External reference offered on a sub-meter?** It is not
answered in section 06.

---

## Screen 29 · Add an asset · 2 Specification — pages 113–115

Same route · chips **EXISTS BEHIND · NEW BUILD** · commitments 14, 26, 27, 28 ·
figure 45 (meter), figure 46 (device)

### What the drawing shows

**Lede:** *"How does it measure, and what will its readings mean?"*
**Section hint under the rail:** *"Get the multiplier wrong and every bill from this
meter is wrong."*

**Meter (fig 45) — two to a row throughout:**

| left | right |
|---|---|
| **Read method** `SET · READ_METHODS` — `AMI` · *"How a reading reaches us."* | **Connection size** `SET · SERVICE_SIZE_CLASSES` — `—` · *"A rate ladder prices by this."* |
| **Multiplier \*** — `1` · *"Multiplied into every reading before billing."* | **Unit of measure \*** `SET · SERVICES · UOM` — `kgal` · *"The unit every quantity carries."* |
| **Register digits** — `9` · *"Digits before the dial rolls over."* | **Manufacturer** — `Badger Meter` · *"Who made it."* |
| **Model** — `M25` · *"Their name for this device."* | **Form / class** — *"As the manufacturer marks it."* **NEW** |
| **Firmware** — *"The version on the device today."* | **Seal #** — *"The seal fitted at installation."* **NEW** |
| **Opening read** — *"The reading on the dial today."* **NEW** | *(empty)* |

Then a bordered callout: **`CHECK IT AGAINST THE METER FACE`** / *"A ×10 meter reading
4,286 means 42,860 units."* Footer: `Save as draft` **NEW** · `← Back` · `Continue`.

**Device (fig 46):** hint *"What the device is connected to, and when it gets looked
at."* Rows: `Linked meter` (*"The meter that measures it."*) | `Export capacity (kW)`
(*"A capacity, never money."*) · `Manufacturer` (*"Who made it."*) | `Model` (*"Their
name for this device."* **NEW**) · `Test interval` — `12`, *"In months."* |
`Certification due` — a date, *"Where a certificate applies."* · `Form / class`
**NEW** | `Seal #` **NEW**. Closing note: *"No multiplier, no unit of measure, no
register digits and no opening read — a device stores no reading, so the fields are
absent rather than dashed. `AST-R-02`."*

**p115 states a rule in its own box:** `manufacturer` and `model` are **two columns and
therefore two fields on every class** — the edit path's single *"Manufacturer / model"*
box with the help *"One line; separate the two with a middle dot."* is named as the
thing that is wrong, and *"the device step captures no MODEL at all."*

### What the code does today

`MeasuringSpecStep` at **line 1067**, `DeviceSpecStep` at **line 1307**.

**Measuring, in code order:** lede `:1082` · `Manufacturer | Model` (2-col, `:1083`) ·
**`Multiplier | Register digits | Unit of measure` (a THREE-column grid, `:1098`)** ·
sub-meter only: `Allocation share | Allocation rule` (`:1153`) · `Opening read |
Read date` (`:1198`) · a `ConsequenceBox` shown only when a reading was typed (`:1226`)
· the multiplier `Note` (`:1234`) · `Device ID / serial | Firmware` (`:1235`) ·
`Meter type` full width (`:1251`) · meters only: `Connection size` full width (`:1281`)
· a `net_metering` checkbox (`:1297`).

**Device, in code order:** lede · `Linked meter` full width (`:1319`) ·
`Export capacity | Recurring test` (`:1335`, and the cadence is a **SELECT over
12 / 24 / 60 months**, `CADENCE_MONTHS` at `:1404`) · `Connection size` when a service
is declared (`:1374`) · `Device ID / serial | Manufacturer` (`:1385`).

### Gaps — screen 29

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| Opening read | a plain field on step 2, marked **NEW** | built — `:1200`, with a read date at `:1208`, a consequence box at `:1226`, and the step-3 refusal **deleted** | — | **YES — `AST-B-14` is BUILT** (PO 2026-09-12, *"Build it as drawn - move it to step 2"*) |
| Allocation share + rule | sub-meter only, marked **NEW** | built — `:1155` and `:1163`, the rule a chooser over one imported list | — | **YES — `AST-B-27`'s allocation half is BUILT** |
| Form / class | a field, **NEW**, on both classes | absent from both spec steps | CONTENT | No. `POST /assets` accepts `form_class` — **no plumbing needed** |
| Seal # | a field, **NEW**, on both classes | absent from both spec steps | CONTENT | No. Accepted already |
| Model on a device | a field, **NEW** | `DeviceSpecStep` asks Manufacturer and **no Model** (`:1385`) | CONTENT | No. **The drawing's own finding is still live** |
| Multiplier row | two to a row | a **three**-column grid (`:1098`) | LAYOUT — rule 38 gives the UI rules the call; **there is no UI rule about column count, so this one is the drawing's** | No |
| Test interval on a device | a free number reading `12`, helper *"In months."* | a `SelectField` over 12 / 24 / 60 (`:1344`) — **the drawing's 96 on step 4 cannot be chosen at all** | CONTENT + WIRING | No |
| Certification due on a device | on **step 2** | on **step 4** (`:1592`) | LAYOUT | No |
| Read method | on step 2 | on step 1 | LAYOUT | No |
| Connection size position | step 2, row 1, beside Read method | step 2 near the bottom, full width | LAYOUT | No |
| Meter type | **not drawn at all** | a `SelectField` at `:1251` | CONTENT — **code has more than the drawing** | n/a |
| Net metering / bidirectional | **not drawn at all** | a checkbox at `:1297` | CONTENT — **code has more** | n/a |
| Opening **read date** | not drawn | a second field at `:1208` | CONTENT — **code has more**, and it is load-bearing (`openingReadNeedsADate`, `:350`) | n/a |
| Multiplier warning as a box | a bordered callout with the heading `CHECK IT AGAINST THE METER FACE` | a plain `Note` (`:1234`) carrying the same sentence plus *"Confirm against the meter face before saving."* | LAYOUT | No |
| Helper text, most fields | one short phrase per field | **Multiplier, Manufacturer, Model, Firmware and Meter type carry none**; Unit of measure and Connection size carry sentences of 14 and 35 words | CONTENT + **rule 33** | No |

**Manufacturer / model.** The wizard already asks for the two as **two fields** on the
measuring class (`:1084`, `:1091`), which is what p115 asks for. The single-box edit
path it criticises is **not** in this section's scope (screens 16–21, section 04) — I
did not verify it and it is not mine to route.

---

## Screen 30 · Add an asset · 3 Assignment — pages 116–117

Same route · chips **EXISTS BEHIND · NEW BUILD** · commitments 26, 27, 28 · figure 47

### What the drawing shows

**Lede:** *"Where is it going, and is it going anywhere yet?"*

1. **Where does it go?** — annotated `FIX · 2`, a two-option segmented control:
   **`To a unit`** (first, and it is the selected one) · **`Leave it in inventory`**.
2. **Premises \*** `TBL · PREMISES · METERING` — **full width**, *"Search premises…"*,
   **no helper.**
3. **Unit \*** `TBL · UNITS · METERING` (left, *"Search units…"*) | **Install date**
   (right, a date field reading `09/11/2026`, helper *"Not in the future."*)
4. **Location note** — **full width**, helper *"Where a technician will find it."*
   **NEW**
5. A bordered callout: **`OR LEAVE IT UNASSIGNED`** / *"Unassigned assets stay in
   inventory and can be assigned later from the registry."*

Footer: `Save as draft` **NEW** · `← Back` · `Continue`.

**"The screen" table (p116):** Spacing — *"R12, two to a row; the location note runs
full width because it is a sentence."* States — *"**To a unit** and **leave it in
inventory** — the second hides the premises and unit pickers rather than dashing
them."* Words — *"**Location note**, not address — the address lives on the premises
and is walked to (hard rule 8)."* Health — **SERVED**, *"Location note is NEW and has
no capture site anywhere today."*

### What the code does today

`AssignmentStep` at **line 1406**.

Lede `:1418` · `SegmentedField` `:1421` labelled **"Assign now?"** with options
**`Into inventory` first** then `Assign to a unit` · a `ConsequenceBox` when the
destination is inventory **and** a service was named (`:1462`, *"{{service}} is not kept
in inventory"*) · when destination is a unit, a **2-column** `Premises | Unit` grid
(`:1464–1483`) · `Install date` in its own 2-column grid whose right half is an empty
comment block (`:1487–1512`) · `RaiseWorkOrderCheckbox` (`:1517`) · a `Note` (`:1522`)
carrying the inventory sentence.

### Gaps — screen 30

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| Location note | a full-width field, **NEW** | **absent** — capturable only on the asset's Lifecycle edit dialog (`AssetPanelEdits.tsx:839`) | CONTENT | Partly. The document's *"no capture site anywhere today"* is **now false**; *"not on this step"* is **still true**. `POST /assets` accepts `location_note` — no plumbing needed |
| Chooser label | **"Where does it go?"** | **"Assign now?"** (`assets.add.assignNow`) | CONTENT | No |
| Chooser option order | `To a unit` first | `Into inventory` first (`:1424`) | LAYOUT | No |
| Chooser option words | `To a unit` · `Leave it in inventory` | `Assign to a unit` · `Into inventory` | CONTENT | No |
| Premises width | full width, on its own row | half width, paired with Unit (`:1464`) | LAYOUT | No |
| Premises required marker | drawn with `*` | not `required`; `stepValid(3)` (`:333`) requires only `unit_id` and `install_date` | CONTENT | No |
| Install date helper | *"Not in the future."* | *"Leave blank while in inventory."* — **a different fact, not a rewording** | CONTENT | No |
| Install date row | paired with Unit | in its own grid whose second cell is empty (`:1487`) | LAYOUT | No |
| Inventory callout | a titled box, `OR LEAVE IT UNASSIGNED` | a plain `Note` with the body only (`:1522`) | LAYOUT | No |
| Work-order checkbox | **not drawn on this step** — the drawing puts it on step 5 | `RaiseWorkOrderCheckbox` at `:1517`, *"Raise an installation work order"* | LAYOUT — **code has it on the wrong step** | No |
| Service-dropped consequence | **not drawn** | a `ConsequenceBox` at `:1462` | CONTENT — **code has more**, and it is honest about a real gap (`OQ-MET-1768`) | n/a |

---

## Screen 31 · Add an asset · 4 Lifecycle — pages 118–119

Same route · chips **EXISTS BEHIND · NEW BUILD** · commitments 26, 27, 28 · figure 48

### What the drawing shows

**Lede:** *"What did it cost, how long should it last, and when is it looked at?"*
**Section hint:** *"These feed the replacement forecast and the certification
calendar."*

Two to a row, four rows:

| left | right |
|---|---|
| **Supplier** — *(no helper)* | **Purchase cost** — *"Stored to four decimals, shown to two."* |
| **Purchase date** — *"Age counts from here when never installed."* | **Depreciation method** `NONE · NO LIST EXISTS` — a dropdown reading `Straight line`, *"How the present value is worked out."* **NEW** |
| **Expected life** — `10`, *"In years."* | **Warranty end** — *"When cover stops."* |
| **Test interval** — `96`, *"In months."* | **Certification due** — *"Where a certificate applies."* |

Footer: `Save as draft` **NEW** · `← Back` · `Continue`.

**"The screen" table (p120):** Primary action — *"`Continue` — to the review, which is
new."* Cognitive load — *"Everything here is optional and everything here feeds
something later."* Health — **SERVED**, *"Depreciation method is NEW."*

### What the code does today

`LifecycleStep` at **line 1527**.

Lede `:1541` · `Supplier | Purchase cost` (`:1542`) · `Purchase date | Cover ends`
(`:1563`) · `Expected life (years) | Certification due` (`:1583`) · measuring only:
`Recurring test` full width, a SELECT over 12 / 24 / 60 (`:1602`) · **a bordered
Summary box** (`:1618`) listing Asset (`number · type · service`), Multiplier, Opening
read when present, and Destination.

### Gaps — screen 31

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| Depreciation method | a dropdown, **NEW**, annotated `NONE · NO LIST EXISTS` | **absent** — capturable only on the asset's Cost & value edit dialog (`AssetPanelEdits.tsx:757`) | CONTENT | Partly — the doc's *"nobody can set it"* is **now false**; *"not at Add"* is still true. `POST /assets` accepts it. ⚠ **The annotation is the real work: no list exists**, so a picker needs a ratified vocabulary first |
| Test interval | a free number reading `96`, *"In months."* | a SELECT over **12 / 24 / 60 only** (`:1602`) — **96 is not offerable** | WIRING | No. The helper says the type's own default is *"meters 96"*, so the code's own copy names a value its control cannot produce |
| Test interval label | `Test interval` | `Recurring test` | CONTENT | No |
| Test interval row | paired with Certification due | full width, alone, after the grids | LAYOUT | No |
| Warranty end label | `Warranty end` | `Cover ends` (`assets.valuation.coverEnds`) | CONTENT | No |
| Expected life label | `Expected life`, helper *"In years."* | `Expected life (years)`, helper *"Whole years — what age and book value are computed from."* | CONTENT — **the drawing splits the unit into the helper, which is rule 33's LABEL ≤ 3 words** | No |
| Purchase date helper | *"Age counts from here when never installed."* | none | CONTENT | No |
| Warranty end helper | *"When cover stops."* | none | CONTENT | No |
| Certification due helper | *"Where a certificate applies."* (4 words) | *"Left blank, it is derived from the last test and the cadence."* (11) | CONTENT + **rule 33** | No |
| Field pairing | Expected life ↔ Warranty end, Test interval ↔ Certification due | Expected life ↔ **Certification due**, Warranty end paired with Purchase date | LAYOUT | No |
| Summary box | **not drawn on step 4** — the drawing replaces it with screen 32 | rendered at `:1618` | LAYOUT — **it is the stand-in for the missing review step** | No |

---

## Screen 32 · Add an asset · 5 Review & add — pages 120–121

Same route · **`POST /assets`** · chip **NEW BUILD** (no *exists behind*) ·
commitments 26, 28 · figure 49

### What the drawing shows

**Lede:** *"Before I create it — is this right?"*
**Line under the rail:** *"Nothing is created until you press **Add asset**. The number
below is reserved at that moment, not before."*

**Two columns of read-only panels, four panels:**

| left column | right column |
|---|---|
| **Identity** — Asset number · Class · Asset type · Serial · External reference | **Measurement** — Multiplier · Unit of measure · Register digits · Opening read |
| **Assignment** — Premises · Unit · Install date | **Cost & value** — Purchase cost · Expected life |

Then the same **`CHECK IT AGAINST THE METER FACE`** callout, then a single checkbox
**`Raise a field work order to install it`**, then the footer:
`Save as draft` **NEW** · `← Back` · **`Add asset ✓`**.

**"The screen" table (p121):** Primary action — *"`Add asset ✓` — the only control in
the whole flow that writes anything."* Write surfaces — *"`POST /assets`, once, here."*
Walked — ⚠ ***"Not walked — this screen is not drawn anywhere in this document today,
and that is the finding: `WizardFrame` already provides a final ✓ commit and every
other wizard in the product gets one. The four steps were drawn and the commit was
not."*** Spacing — *"two columns of panels at 16."* Cognitive load — *"grouped the way
the **Overview** groups it — Identity · Assignment · Measurement · Cost & value — so a
person reviews in the shape they will later read."* States — **Failed** —
*"The asset was not created."* and every value still typed. Health — **UNVERIFIED**,
*"nothing here is drawn from a running screen, because this step has never been drawn."*

### What the code does today

**The screen does not exist.** There are four steps, not five
(`ADD_STEP_COUNT = 4` at `:113`; the `steps` array at `:731` has four entries), so
`WizardFrame` treats **step 4 — Lifecycle — as the final step** and renders the commit
there (`WizardFrame.tsx:858 isFinalStep`). The commit label is `Add asset ✓`
(`assets.add.commit`) ✓ and `commit()` at `:684` calls `createAsset(addPayload(values))`
once ✓, so the write is right; what is missing is the screen in front of it.

What stands in for the review is the **Summary box** on step 4 (`:1618`), and it
carries **four facts**: the asset line (`number · type · service`), the multiplier, the
opening read when one was typed, and the destination as a word.

A person therefore commits from a form, not from a review. `stepFromParam` clamps
`?step=5` to 4 (`:120`), so the address cannot reach a fifth step either.

### Gaps — screen 32

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| The step itself | a fifth step, `5 Review`, with its own rail box | four steps; the commit rides on step 4 | **MISSING SCREEN** | No — **the document's finding is exactly right at 2.261.3** |
| What is reviewed | **four grouped panels, ~14 facts** in the Overview's own grouping | a summary box with **4 facts** (`:1618`) | CONTENT | No |
| Grouping | Identity · Assignment · Measurement · Cost & value | none — a flat four-row box | LAYOUT | No |
| The reservation sentence | *"Nothing is created until you press Add asset. The number below is reserved at that moment, not before."* | nothing says when the number is taken | CONTENT | No |
| Multiplier warning repeated at the commit | the callout appears again on step 5 | appears on step 2 only (`:1234`) | LAYOUT | No |
| Work-order checkbox | on step **5**, *"Raise a field work order to install it"* | on step **3** (`:1517`), *"Raise an installation work order"* | LAYOUT + CONTENT | No |
| Commit button | `Add asset ✓` | `Add asset ✓` ✓ | — | correct already |
| Failure state | *"The asset was not created."*, values preserved | `WizardFrame.tsx:832 FailedWithRetry` preserves the step content ✓; the sentence comes from the server's `message_key` (`:707`) | — | correct already |
| Test coverage | — | **no test asserts a review step, because there is none.** `AssetAddWizardFixes.dom.test.tsx` has 19 cases and none names step 5 | — | n/a |

**Plumbing needed: none.** `POST /assets` is unchanged, `WizardFrame` already supports
an arbitrary step count, and the final-step commit is generic. This is a front-end step
and the facts it shows are all already in `AddWizardValues`.

---

## Screen 33 · Drafts — pages 122–124

`/:tenant/assets?drafts=1` — **PROPOSED** · `GET /wizard-parks?flow=add_asset,retire_asset`
· chip **NEW BUILD** · commitment 28 · figure 50

### What the drawing shows

**Lede:** *"What did I start and not finish?"*

The registry page, with two controls above the title: a red **`DRAFTS 4`** and an
outlined **`+ ADD ASSET`**. Title **Assets**, and the tab strip
`Meters · Sub-meters · Behind the meter · Inventory · Lifecycle · Map`.

Below it a section headed **Drafts** with a **`4 waiting`** chip, and the description
*"Started and not finished. **Nothing here has happened yet** — an add has taken no
number and a retire has not retired anything."*

A table of five columns — **WHAT IT IS · ACTION · STOPPED AT · WAITING · SAVED BY** —
with per-row **`Resume`** and **`Discard`** drawn as two outlined **text buttons**. Four
illustrative rows, mixing `Add · Meter`, `Add · Sub-meter`, `Retire` and `Add · Device`,
with `2 of 5 · Specification`, `1 of 5 · Identity`, `2 of 3 · Replacement`,
`3 of 5 · Assignment`. Footer line: *"A draft is discarded by whoever saved it, or when
it is finished. Nothing expires it."* **No pagination footer is drawn.**

### The ruling behind it, quoted from pages 123–125

> **PO 2026-09-11:** *"Keep save as draft button and make entry with status draft"*,
> then *"for now give same treatment"* for retire.
>
> *"Both wizards now carry one exit and it is `Save as draft` — the five add steps and
> the three retire steps. The two it replaces were wrong on both: **Save & exit** wrote
> nothing at all … and **Park** asks *what are you waiting on* from nine reasons that
> belong to the customers' world, none of which is why a meter install or a removal
> stalls."*
>
> *"Where the draft goes is settled law, not a new decision. `BR-SHL-048`, ruled by the
> PO on 2026-08-26: **"Option A - Unitl move in executed, no records updates."** A
> half-finished wizard is a saved draft of a FORM, held in `wizard_parks`, and nothing
> it describes is touched until it commits."*
>
> *"So the draft is a row with the status — a `wizard_parks` row IS a draft; existence
> is the status — **and nothing else moves.** On an add: the asset number is still only
> taken at the end, so an abandoned draft leaves no gap in the tenant's series … On a
> retire: **the asset goes on working.**"*
>
> **The draft carries** *"copied values, never a foreign key, deliberately, so that a
> forgotten draft can never block a delete or hold a row still."* Resume therefore
> *"re-reads the asset and checks it before drawing step 1"*, and a retire draft whose
> asset is already terminal *"says so and offers only **Discard**"* (`BR-AST-030`).

**What it takes to build, as the document states it (p124):** *"One tuple grows by
two. `WIZARD_PARK_FLOWS` is (`move_in`,`move_out`,`transfer`,`disconnect`,
`new_connect`) — add `"add_asset"` and `"retire_asset"`. No new table, no migration to
`assets`, no new endpoint."* · *"`waiting_on` is free text with a not-empty check, so a
plain draft writes the constant `draft`."* · *"Both asset wizards pass `WizardFrame`'s
`exit` prop, which **neither passes today**."* · **The home** — *"a `Drafts` control in
the registry header with its count … **This is the half that must not be skipped**: the
five customer flows each name a home, and a draft with none is a row nothing can
reach."*

### What the code does today — every claim verified

| claim | verdict | evidence |
|---|---|---|
| `wizard_parks` exists, with copied values and no FK to the subject | **TRUE** | `apps/tenancy/models.py:1789 subject_label` (TextField), `:1792 subject_ref` (JSONField), and the model's own note at `:1740` — *"stored inside `subject_ref` as COPIED VALUES"* |
| `WIZARD_PARK_FLOWS` is the five, enforced in the schema | **TRUE** | `apps/tenancy/models.py:1717`, and `ck_wizard_parks_flow` at `:1825`. **So `add_asset` is a MIGRATION, not a client change** |
| `waiting_on` is free text with a not-empty check | **TRUE** | `models.py:1806` TextField, `ck_wizard_parks_waiting_on` at `:1832`, `_clean_waiting_on` at `wizard_parks.py:199` |
| No new endpoint is needed | **TRUE** — five routes already exist | `apps/tenancy/wizard_parks_api.py` (POST/GET list, GET/PATCH/DELETE item), registered at `config/urls.py:75` |
| *"Both asset wizards pass `exit`, which neither passes today"* | **STALE — both pass it now** | `AssetAddWizard.tsx:869` and `AssetRetireWizard.tsx:438`. **But what they pass is `Save & exit` plus a `Park` disabled over *"Drafts are not kept yet."*** — so the button is there and saves nothing, which is the *"promise the product does not keep"* the spec names |
| There is no Drafts home on the registry | **TRUE** | `AssetRegistryPage.tsx:797` builds **seven** tabs (`meters · sub_meters · behind_the_meter · inventory · lifecycle · map · imports`) and no Drafts control; `?drafts=1` is read by nothing — the page reads only `TAB_PARAM` (`:468`). A repo-wide grep for `drafts` in `07-frontend/src` returns no assets hit |
| The refusal cannot rot silently | **TRUE, and it is a good one** | `AssetWizardExit.dom.test.tsx:199` — *"no asset flow is in the park store's vocabulary yet"* — fails the day `add_asset` is added. That is hard-won law 2's mirror applied correctly |

⚠ **One route in the drawing does not work as written.**
`GET /wizard-parks?flow=add_asset,retire_asset` cannot be served: the list filter takes
a **single** flow through `_clean_flow`, which refuses anything not in the five
(`apps/tenancy/wizard_parks.py:343` and `:176`). A comma list 422s. Either the filter
grows a multi-value form or the screen makes two calls — **a real decision, and small.**

⚠ **A pagination observation for whoever builds it.** `GET /wizard-parks` materialises
the whole queryset and paginates the Python list
(`wizard_parks_api.py:147–152` — `service.list_parks(...)` then
`paginator.paginate_queryset([...])`). At T7 that is one or two rows and harmless; it
is the same shape `NFR-3` names, so do not copy it outward.

### Gaps — screen 33

| gap | drawing says | code says | class | already fixed since 2.234.17? |
|---|---|---|---|---|
| The screen | a Drafts list on the registry with five columns and two row actions | **does not exist**; `?drafts=1` is read by nothing | **MISSING SCREEN** | No |
| The `Drafts N` control | a counted control in the registry header | absent (`AssetRegistryPage.tsx:797`) | **MISSING SCREEN** | No |
| `Save as draft` | one exit on all five add steps and all three retire steps | `Save & exit` (writes nothing) + a `Park` **disabled** over *"Drafts are not kept yet."* | **MISSING PLUMBING** | No |
| The flow vocabulary | `add_asset` + `retire_asset` | five values, enforced by `ck_wizard_parks_flow` | **MISSING PLUMBING — a migration** | No |
| The list filter | `?flow=add_asset,retire_asset` | single-value only; a comma list 422s (`wizard_parks.py:176, 343`) | **MISSING PLUMBING** | No |
| Retire resume re-reads its asset | *"resume re-reads the asset and checks it before drawing step 1"*; a terminal asset offers only `Discard` | nothing resumes anything | **MISSING PLUMBING** | No |
| Row actions | `Resume` and `Discard` as outlined **text buttons** | n/a | **rule 38 divergence** — **B14 rule 15 wins: row actions are ICONS with tooltips, never text links**, max 2 visible. Record it; do not build the text buttons | n/a |
| Pagination | no footer drawn | n/a | **rule 38 divergence** — **B14 rule 16 wins: a pagination footer on every list table.** The wizard-summary exemption does not apply; this is a list | n/a |
| Empty state | not drawn | n/a | **B14 rule 17** — the drawing shows only a populated table; an empty state is required and is not the drawing's to omit | n/a |
| Tab strip | six tabs drawn | seven exist — `Imports` is live and is **out of this blueprint's scope** by instruction | — | not a gap. Do not remove a tab on this drawing's authority |

---

## Summary — the counts

**What was read.** 17 PDF pages as images (108–125), page 109 at scale 4. Five code
files censused: `AssetAddWizard.tsx` (1,667 lines), `assetsShared.tsx`,
`AssetRegistryPage.tsx`, `AssetPanelEdits.tsx`, `WizardFrame.tsx`, plus four backend
modules and the four named test files (1,937 lines, **56 cases** — 19 · 4 · 20 · 13).

**Screens.** 6 in scope. **2 do not exist at all** (32 Review & add, 33 Drafts).
**4 exist and diverge** (28, 29, 30, 31).

**Gaps.** **71 rows** across the six gap tables — 15 · 15 · 11 · 11 · 9 · 10. By class,
each row counted once by its primary class (two rows carry a second class and are named
in the footnote, so the column sums to 73 over 71 rows):

| class | count | what it means |
|---|---|---|
| CONTENT | 30 | a label, a helper, a marker or a missing field — no new plumbing |
| LAYOUT | 22 | a field on the wrong step, the wrong row, the wrong width or the wrong order |
| MISSING PLUMBING | 5 | every one belongs to Drafts: the flow migration, the multi-flow filter, the `Save as draft` button (counted once, though it appears as screen 28's footer row too), the retire resume, and the parked-draft home |
| **already fixed since 2.234.17** | **4** | see below |
| correct already, or not a gap | 4 | the commit label, the failure state, a test-coverage note, and the seventh registry tab |
| MISSING SCREEN | 3 | screens 32 and 33, and the registry's Drafts control |
| rule-38 divergences (recorded, not built) | 3 | text row actions, no pagination footer, no empty state on the Drafts table |
| WIRING | 2 | the test-interval select cannot produce a value its own helper names (steps 2 and 4) |

*The two double-counted rows:* screen 28's footer (CONTENT **+** MISSING PLUMBING) and
screen 29's device test interval (CONTENT **+** WIRING).

**Five of the 30 CONTENT rows run the other way** — the code has something the drawing
does not: the number-availability note, Meter type, the net-metering checkbox, the
opening-**read date**, and the *"not kept in inventory"* consequence. They are listed so
nobody deletes one to match a picture.

**Four of the document's as-built claims are already wrong, and all four are wrong in
the same direction — the product moved forward:**

1. **`AST-B-03` is BUILT.** The utility service is a picker over
   `GET /settings/services`, not a text box (`AssetAddWizard.tsx:640, 1040`;
   `DEF-MET-4980/4981`). The endpoint is `AnyTenantRole`
   (`apps/tenancy/api.py:417`) exactly as the document's own correction says.
2. **`AST-B-14` is BUILT.** The opening read is an ordinary field on step 2 with its
   read date beside it, and the refusal was **deleted** from step 3 rather than
   un-disabled (`:1200`, `:1208`; `AssetAddWizardFixes.dom.test.tsx:343`).
3. **`AST-B-27`'s allocation half is BUILT** at Add for sub-meters (`:1155`, `:1163`).
4. **The "seven columns with no capture site anywhere" is ZERO.** All seven are now
   writable — three at Add, and `external_ref`, `form_class`, `seal_no`,
   `location_note`, `depreciation_method` and `loss_tolerance_pct` on the asset's own
   edit dialogs (`AssetPanelEdits.tsx`, mounted at `AssetDetailPage.tsx:634`).
   **The wizard now captures 28 asset columns, not 26**, and `AddWizardValues` holds
   **33 keys** against the document's measured 29.

**What has NOT moved:** seven of the ten are still not capturable **at Add**, which is
`AST-B-27`'s actual argument — a seal, a location note and an external reference are
facts a person holds while installing, and the product now makes them come back for a
second screen.

**The three biggest, in order:**

1. **Screen 32 does not exist.** A clerk commits `POST /assets` from a form, reviewing
   four facts in a summary box, where the drawing gives them four grouped panels of
   about fourteen. It needs **no backend work at all** — `WizardFrame` already takes
   any step count and already renders the final ✓.
2. **Screen 33 does not exist, and it is the only thing in the section with real
   plumbing behind it** — a migration to `WIZARD_PARK_FLOWS`, a multi-flow list filter,
   the `Save as draft` button on eight steps across two wizards, and the registry home
   without which, in the spec's own words, *"a draft is a row nothing can reach."*
   Meanwhile `Save & exit` sits on every step **writing nothing**, which is the
   condition the PO's *"Keep save as draft button and make entry with status draft"*
   was given to end.
3. **Fields are on the wrong steps, both ways.** Read method is drawn on step 2 and
   built on step 1; Device ID / serial is drawn on step 1 and built on step 2;
   Certification due is drawn on step 2 for a device and built on step 4; the
   work-order checkbox is drawn on step 5 and built on step 3. Each is cheap on its own
   and together they are why the built wizard and the drawn one do not read as the same
   screen.

**Two things the code has that the drawing does not, and both look deliberate rather
than accidental:** the number-availability note on step 1, and the
*"{{service}} is not kept in inventory"* consequence on step 3 — which names a real,
open gap (`OQ-MET-1768`, an unassigned asset's service has no column to live in).
Neither should be deleted to match a drawing.

**Copy.** Seven helper strings breach B14 rule 33's six-words-per-sentence cap, and in
**every one of the seven the drawing's replacement is compliant** — the asset number,
serial, unit of measure, connection size, certification due, expected life and test
cadence helpers. On this section's copy the drawing and B14 agree, which makes those
seven the cheapest rows in the whole table.

**Nothing here is built and no register was touched.** Every id needs a real repo
allocation before it is cited in code; `AST-B-##` is this document's own series and is
not repo-live.
