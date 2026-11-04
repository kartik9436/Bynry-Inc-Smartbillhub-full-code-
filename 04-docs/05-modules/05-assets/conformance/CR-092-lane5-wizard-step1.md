# CR-092 lane 5 · Adding an asset — the wizard and its draft behaviour, STEP 1, identify only

**Read on** 2026-09-11 · **branch** `claude/hi-0jmv62` · **tip at dispatch** `0a1a677d9`, synced to
`613afe4e0` before filing · **version** `2.237.0`
**Source document:** the Assets-menu blueprint (artifact `2f979496`), **section 06** (screens 28–33),
**section 07** (journey J5) and the `AST-B-03 / -14 / -27 / -28` cards.
**Scope:** `07-frontend/src/features/assets/AssetAddWizard.tsx` (1,150 lines) and the draft behaviour
that reaches `AssetRetireWizard.tsx` (screens 24–26). The Imports tab and `AssetImportWorkflow.tsx`
are out of scope and are not mentioned again.

**This lane changed no component, catalogue, route, stylesheet, gate, test, rule, epic, question or
story.** It read code, built a stack, drove the wizard, measured, created three real assets, wrote
this file and filed defect rows.

---

## 0 · The paragraph step 2 should read first

**The blueprint's section 06 was written from a source read.** Its own screen tables say so, seven
times: *"Not walked as redrawn"* on screens 28, 29, 30, 31, and *"Not walked — this screen is not
drawn anywhere in this document today"* on 32. Only two rows in section 07 touched this wizard at
all. **This lane drove it end to end and created assets through it**, and that turned up four things
a read could not reach — one of which is a billing-affecting value being silently discarded on the
wizard's own default path (`DEF-MET-4986`).

**The single most consequential correction:** the blueprint's `AST-B-14` carry-over table says the
**Opening read** field is *"UNCHANGED … the same field in the same place"* with *"moved 0"*. It is
not in the same place. **It is on step 3 (Assignment), not step 2 (Specification)** — beside
*Install date*, where neither the register digits nor the unit of measure a reading needs are
visible. Building `AST-B-14` to its own drawing is a MOVE plus an enable, and the reconciliation
arithmetic printed under Figure 55 does not describe the change it is asking for.

---

## 1 · How this was produced — the commands, so step 2 can repeat them

No stack was running on 8401 or 8000 when this lane started (TCP probe: connection refused on both).
So one was built, on private ports, against the repo's own PostgreSQL 16 cluster:

```
pg_ctlcluster 16 main start
06-backend $ DJANGO_SETTINGS_MODULE=config.settings.local \
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub \
    python3 manage.py showmigrations --plan        # 338 applied, 0 pending — no migrate needed
06-backend $ … manage.py runserver 127.0.0.1:8451 --noreload
07-frontend $ npx vite build                       # exit 0, 22.85s
07-frontend $ PORT=8452 API_PROXY_TARGET=http://127.0.0.1:8451 node server.mjs
```

Driven in Chromium (`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`, resolved through
`createRequire("/home/user/SMARTBillHub/07-frontend/package.json")` → `playwright-core`), signed in
as `dana@brazosbendutilities.com` (System Admin) on tenant `brazosbend`, **at 1440 and at 1280**.
The five driver scripts are in this session's scratchpad at `cr092/lane5-drive*.mjs` and
`cr092/lane5-measure.mjs`; every figure below names the run that produced it.

⚠ **THE SEED IS NOT WHAT THE BRIEF SAID, AND IT IS NOT WHAT THE BLUEPRINT WALKED.** The brief and the
blueprint both describe `brazosbend` as **126 assets, 73 premises, 121 units, 72 accounts**. On this
database `brazosbend` holds **11 assets, 6 premises, 10 units, 1 account, 1 user** — and it is
`oak-ridge` that holds 73 / 121 / 72 (74 assets), with `pine-hill` at 135 / 77 / 125 / 73. So the
tenant the blueprint walked was seeded under a name this database now gives to something much
smaller. **Nothing below depends on the row count** — the wizard creates rather than lists — but a
lane that re-runs a KPI or pagination measurement on `brazosbend` will get different numbers than
the blueprint did, and should use `pine-hill` or `oak-ridge` instead.

**Writes made by this lane, named so nobody mistakes them for seed:** `LANE5-MASTER-1` (meter, left
in inventory), `LANE5-SUB-1` (sub-meter under `M-7001`), `LANE5-ASSIGNED-2` (meter assigned to
`1408 Bluestem Ln · Unit A`). Two further attempts were **refused by the server and wrote nothing**:
one with `service` empty (422 `assets.service_required`) and one with `service=watr-typo`
(422 `assets.service_not_enabled`).

---

## 2 · Baseline re-check — the CR asks each lane to re-check the file it writes about

`git diff --numstat 79c659d7d HEAD` over the six files this document makes claims about printed
**nothing** for any of them:

```
07-frontend/src/features/assets/AssetAddWizard.tsx        identical
07-frontend/src/features/assets/AssetRetireWizard.tsx     identical
07-frontend/src/features/assets/AssetRegistryPage.tsx     identical
07-frontend/src/components/WizardFrame.tsx                identical
06-backend/apps/assets/services.py                        identical
06-backend/apps/tenancy/api.py                            identical
```

So every as-built statement the blueprint makes about this wizard still holds on this tip, and the
statements below are about the same bytes.

**And the register count, which the CR asks each lane to settle by counting rather than by quoting:**
`grep -o 'id="spec-AST-B-[0-9]*"' | sort -u | wc -l` → **24**. Numbers 07, 08, 09 and 17 are absent
(withdrawn and not reused). The closing paragraph's *"Twelve live specifications"* is wrong; the
table is right.

---

## 3 · Screen 28 — Add an asset · 1 Identity

**Route driven:** `/brazosbend/assets/new?class=meters`, reached by clicking **+ Add asset** on the
registry, not by typing the address.

### What the blueprint claims, and what the product does

| blueprint | driven, at 1440 and 1280 |
|---|---|
| The wizard is a **page**, not a dialog, at `/:tenant/assets/new?class=` | ✔ confirmed |
| **Five** steps — `1 Identity · 2 Specification · 3 Assignment · 4 Lifecycle · 5 Review` | ✘ **FOUR.** `ADD_STEP_COUNT = 4` (`AssetAddWizard.tsx:93`) and the rail renders four. Screen 32 is a new build and the blueprint says so; the five-step rail in Figures 43–49 is therefore a REMEDY drawing, not the product |
| The class chooser is first and branches on three classes | ✔ `SegmentedField` over `ASSET_TAB_IDS` = `meters · sub_meters · behind_the_meter` |
| A sub-meter makes **Parent master** required | ✔ rendered only on `?class=sub_meters`, labelled `Parent / master meter*`, and `stepValid(1)` refuses without it |
| **Utility service** is on this step and is a **plain `TextField`** | ✔ and this is `AST-B-03` — see below |
| `offersConnectionSize()`: a device gets a connection size **only once a service is entered** | ✔ **walked, which the blueprint could not do.** On `?class=behind_the_meter` with type *Backflow preventer* and Service empty, step 2 renders five controls and no **Connection size**; going back, typing `trash`, and continuing renders six, **Connection size** among them |
| The header title is the asset number, with *"Not created yet · the number is reserved when you finish"* | ✘ remedy. The product renders `h1` **"Add an asset"** at 32px with kicker "Assets" |
| **External reference** is drawn on step 1 | ✘ remedy — no such control exists; it is `AST-B-27` |

### The field census, as rendered (`?class=meters`)

```
id           label                 DOM order             label→input   helper words
asset_no     Asset #               label→helper→input    29px          17  (10 once a number is suggested)
type         Asset type*           label→input            5px           0
read_method  Read method           label→input            5px           0
service      Service               label→helper→input    29px          14
```
`?class=sub_meters` adds `parent_asset_no` (`Parent / master meter*`, 29px, 13 words).

### AST-B-03 — the utility service is picked from the tenant's enabled list, not typed

**Status: confirmed, and the remedy is cheaper than the blueprint says. Filed as `DEF-MET-4980`.**

* The control is `<input type="text">` with **`placeholder` null and `list` null** — no datalist, no
  options, nothing to open. `AssetAddWizard.tsx:702-708`.
* Its help is *"The service code this asset measures. It must be one your utility has enabled."* —
  14 words that name a list and do not show it.
* **`GET /settings/services` is never called.** A complete four-step walk issued **12 distinct API
  calls** (`lookups/asset_types`, `lookups/read_methods`, `lookups/meter_types`,
  `lookups/service_size_classes`, `premises`, `units`, `assets?f.tab=meters`,
  `assets/number-preview` ×2, `me`, `shell/display`, `in-app-messages`) and **none** of them was
  `/settings/services`.
* The endpoint is **`AnyTenantRole`** — `apps/tenancy/api.py:419`, `@permission_classes([AnyTenantRole])`,
  commented *"clerks read-only; writes below"*. Fetched live as the signed-in owner: **200**, eleven
  service rows with their `enabled` flags. On `brazosbend` exactly **two** are enabled (`electric`,
  `water`), so the picker would offer two of eleven.
* **`getTenantServices` already has 25 non-test caller files** — including
  **`AssetRegistryPage.tsx:507`**, the page the `+ Add asset` button sits on, where the same list is
  the service **filter's** vocabulary under the comment *"the service filter's vocabulary is the
  TENANT's enabled set"*. The list a clerk needs is one click behind them, as a dropdown, and
  becomes a text box when they open the form.

⚠ **THE BRIEF ASKED WHETHER THIS IS A THIRD HAND-TYPED SERVICE LIST. IT IS NOT, AND THE DIFFERENCE
DECIDES THE FIX.** `AssetAddWizard.tsx` contains **zero** hardcoded service codes (every grep hit is
a comment or `fireToast`). Contrast `SignupWizard.tsx:121-133` and `ratingShared.tsx:430-480`, which
each carry a hand-typed eleven-entry list — the two places CLAUDE.md names, where a twelfth service
*"does not appear on screen on its own and it fails SILENTLY"*. So:

* **their** failure mode is a list that goes stale — a new service exists and no screen offers it;
* **this** failure mode is no list at all — every code is offered, including `watr-typo`, and the
  server refuses it after the person has moved on;
* **therefore the remedy is the endpoint, and writing an eleven-item array here would MANUFACTURE
  the third instance of hard-won law 2** — a third place to forget. `ServicesAvailableField.tsx`
  (features/metering) is the shape to copy: one component, `getTenantServices`, filtered to
  `enabled`.

**Two things the blueprint did not record, both filed:**

1. **`AssetAddWizard.tsx:1148`'s own `exceptions:` footer carries the false claim too.** The
   blueprint corrected *"GET /settings/services is System-Admin-only"* where it found it, at
   `AssetRegistryPage.tsx:1515`. The same sentence is in the footer of **the file a lane would
   edit** — *"the service entry stays FREE TEXT against enabled codes (GET /settings/services is
   System-Admin-only; the server refuses an unenabled code)"*. A lane that opens this file to build
   the picker reads that first and concludes it cannot. A third, hedged mention sits at
   `AssetRegistryPage.tsx:303-305`. **`DEF-MET-4982`.**
2. **The field is not marked required and the server requires it.**
   `_check_measuring_requirements` (`apps/assets/services.py:977`) refuses every measuring type
   without a service, by name. `stepValid(1, values)` requires only `type` (and a sub-meter's
   parent). **Driven:** chose `type=meter`, left Service empty, pressed Continue three times — the
   button was never `disabled` and never `aria-disabled` — reached step 4, pressed **Add asset ✓**,
   and `POST /api/brazosbend/assets` answered **422 `VAL-001 assets.service_required`**. The wizard
   rendered *"Failed — The asset was not created. Choose the service this asset measures."* **on
   step 4**, three steps from the empty field, naming the field and not the step. The verb is
   *Choose*, for a control that offers nothing to choose from. **`DEF-MET-4981`** — and note it
   **survives** `AST-B-03`: a picker that is not required refuses just as late.

### J5's two rows, re-driven

**Row 1 — the service control.** *"`<input type="text">`, no placeholder, no options."* **Correct**,
verified at both widths.

**Row 2 — Continue with nothing filled. The blueprint corrected itself here and the correction
STANDS; it does not over-correct.** Driven: pressed **Continue** on a virgin step 1. The button
carried neither `disabled` nor `aria-disabled`; the page stayed at
`/brazosbend/assets/new?class=meters` (no `step=` appeared); and a `role="alert"` rendered

> *"This step isn't finished. Fill in what's marked above, then press Continue again."*

That is `BR-SHL-025`'s posture — answer at the button rather than disable it — and it is right.
**But it is only correct about what it can see:** *"what's marked above"* is `Asset type*` alone, and
the server also requires `Service`, which carries no marker. So the sentence is true and the screen
it describes is incomplete, which is `DEF-MET-4981` and not a reversal of the correction.

---

## 4 · Screen 29 — Add an asset · 2 Specification

### Measuring variant (`?class=meters`, `?class=sub_meters`), as rendered

```
manufacturer       Manufacturer            label→input            5px    0 words
model              Model                   label→input            5px    0
multiplier         Multiplier*             label→input            5px    0
register_digits    Register digits         label→helper→input    29px    7
unit               Unit of measure*        label→helper→input    47px   15
serial_no          Device ID / serial #    label→helper→input    47px   17
firmware_version   Firmware                label→input            5px    0
meter_type         Meter type              label→helper→input    29px   12
size_class         Connection size         label→helper→input    47px   36   ← the worst string in the module
net_metering       Bidirectional — measures export as well as import   (checkbox)
```

Plus the product's own multiplier warning, which the blueprint praises and which is exactly where it
says it is.

### Device variant (`?class=behind_the_meter`), as rendered

```
parent_asset_no      Linked meter            29px   12 words
export_capacity_kw   Export capacity (kW)    29px    9
test_interval_months Recurring test          47px   15
size_class           Connection size         29px    6     ← only once a service is named on step 1
serial_no            Device ID / serial #     5px    0
manufacturer         Manufacturer             5px    0
```

**Confirmed: the device step captures no MODEL at all.** The blueprint says this in prose and does
not carry it into its own ten-row table; a *Watts Water 909* can be displayed on the detail page and
entered nowhere. That is the eighth column with a reader and no writer, and it is variant-specific.

**Not in the blueprint — filed as `DEF-MET-4985`:** `DeviceSpecStep` draws every device field for
every device type, and two of its helpers are written for one type. A **backflow preventer** is
offered *Export capacity (kW)* under the sentence *"A capacity, in kW — inverters and batteries
only."*, and *Linked meter* under *"An exporting inverter links to the net meter that measures its
export."* Both are short — 9 and 12 words — so this is **not** `AST-B-26`; they are about a
different device than the one on screen.

**Also confirmed, and already filed elsewhere:** the **Connection size** picker offers **65 options
spanning every service** — `Fire line 2"`, `Trash 96-gallon cart`, `Broadband 500 Mbps`,
`Thermal chilled water 800 tons` — on a WATER meter. The file says so itself and points at
**`DEF-3300`**; it is not re-filed here.

### AST-B-14 — a meter booked in can record the reading on its dial

**Status: the column and the service path both check out. The blueprint has the field on the wrong
step.**

* **Verified the column:** `meter_reads` is metering's, and the create-time write would go through a
  seam. The precedent the blueprint names is real — `metering.services.capture_final_read` commits a
  manual read inside the caller's transaction and refuses the whole operation when it cannot
  (`apps/metering/seams.py`, wired by the CR-028 debt sweep, and `apps/assets/services.py`'s
  `_reassign_inner` / `retire_asset` both pass an actor through it). So `AST-B-14` is that same
  shape at the other end of the asset's life, as claimed.
* **The field is on step 3, not step 2.** `AssetAddWizard.tsx:1002-1009` renders it inside
  `AssignmentStep`. Driven: `?class=meters&step=3` shows exactly two controls — `install_date` and
  `opening_read` — and `?step=2` shows neither. `AST-B-14`'s card says *"Screens 29"* and its
  Figure 55 draws it on step 2 *"where the register digits and the unit of measure already sit"*.
  **Both of those are on step 2 and the opening read is not.** The carry-over table's *"moved 0"*
  and *"the same field in the same place"* are wrong, and the figure reconciliation printed under it
  (`As-built fields 9 … Remedy fields 11`) describes a step-2 field list the product does not have.
  Step 2 on this tip has **nine** measuring fields and none of them is the opening read.
* **The field is `readOnly`, not `disabled`, and does not look refused.** Measured with
  `getComputedStyle` at both widths: `background rgb(234,233,233)`, `color rgb(32,30,29)`,
  `cursor: text`, `tabIndex 0` — byte for byte the same as *Install date* beside it and as all 22
  other inputs in the wizard. A clerk tabs in, sees an ordinary box, types, and nothing appears; the
  only thing that says why is a 19-word helper **above** the box. The file's own comment and the
  blueprint both call it *"DISABLED with the reason"*. **`DEF-MET-4984`** — separate from
  `AST-B-14`, because if that slips this is what ships.

---

## 5 · Screen 30 — Add an asset · 3 Assignment

```
(segmented)   Where does it go?   →  "Into inventory" (DEFAULT) · "Assign to a unit"
premises_id   Premises            only when "Assign to a unit"   (SearchSelectField)
unit_id       Unit*               only when "Assign to a unit"   (SearchSelectField)
install_date  Install date        29px    5 words   [date, min=null, max=null]
opening_read  Opening read        47px   19 words   readOnly
(checkbox)    Raise an installation work order
(note)        the inventory note
```

* The blueprint's two states are right: choosing *Into inventory* **hides** the premises and unit
  pickers rather than dashing them. Driven both ways.
* **Location note** is not here. It is `AST-B-27`.
* The blueprint draws the **raise-a-work-order** tick on its new step 5; the product has it here, on
  step 3.
* The premises picker offered `1408 Bluestem Ln · P-00001` and the unit picker
  `1408 Bluestem Ln · Unit A/B`, scoped to the chosen premises — `unitsFor()` works as written.

### ⚠ The finding that needed a write, and is in no blueprint row

**The utility service the wizard requires on step 1 is discarded on the default path.**

Two real meters created through the wizard, same field, same typed value `water`:

| asset | step 3 | what came back |
|---|---|---|
| `LANE5-MASTER-1` | **Into inventory** (the default) | `status: inventory`, **`service: null`**, `service_point_id: null` |
| `LANE5-ASSIGNED-2` | Assign to a unit (`1408 Bluestem Ln · Unit A`, install `2026-09-11`) | `status: active`, **`service: "water"`**, `service_point_id: 01a08ad1-559c-…` |

**The mechanism:** `assets` has **no `service` column**. `apps/assets/selectors.py:707-711` derives
it — `_service_of()` returns the service POINT's service or `None` — and
`apps/assets/services.py:1036-1037` only calls `seams.ensure_service_point(unit_id, service_code)`
`if unit_id and service_code`. So the value is validated against the tenant's enabled list, the whole
form is refused when it is missing or unenabled, and then it is thrown away unless step 3 assigns
the asset.

The backend knows: `services.py:968-973` says *"The unassigned service declaration has no column to
live in; that gap is reported, not invented around."* **The screen says nothing**, the wizard's
default destination is inventory, and the blueprint's own drawing tags this field *affects billing*.
**`DEF-MET-4986`.** Step 2 must decide this before building `AST-B-03`, because a picker that
politely discards its answer is not an improvement.

---

## 6 · Screen 31 — Add an asset · 4 Lifecycle

```
supplier              Supplier                 5px    0 words
purchase_cost         Purchase cost           29px    7        "Stored to 4 decimals, shown to 2."
purchase_date         Purchase date            5px    0        [date, min=null, max=null]
warranty_end          Cover ends               5px    0        [date, min=null, max=null]
expected_life_years   Expected life (years)   29px   11
certification_due     Certification due       29px   12        [date, min=null, max=null]
test_interval_months  Recurring test          29px   15        (measuring classes only)
```
plus the r10 summary box (`data-add-summary`), which renders asset · multiplier · destination and
carries **no GL line** — §10-D3 is honoured.

* **Depreciation method** is not here. `AST-B-27`.
* The blueprint's `src` tag for it reads *"none ▸ no list exists"*, which is correct: nothing in the
  repo enumerates the methods, so `AST-B-27` needs a ratified list for this one and not just a field.
* The commit is **here**, at the foot of step 4 — `Back` and `Add asset ✓` — not behind a review step.

---

## 7 · Screen 32 — "5 Review & add" does not exist, and neither does a clamp on the URL

The blueprint marks screen 32 **UNVERIFIED** and says so plainly: *"this screen is not drawn anywhere
in this document today … The four steps were drawn and the commit was not."* Confirmed — there is no
fifth step and `WizardFrame` renders the commit at the foot of the last declared step.

**What driving added:** `stepFromParam` clamps the value it USES and never rewrites the address.

```
?step=5   → renders step 4, URL still says step=5
?step=9   → renders step 4, URL still says step=9
?step=abc → renders step 1, URL unchanged
?step=0   → renders step 1, URL unchanged
?step=-1  → renders step 1, URL unchanged
```

**And the same split loses everything a clerk typed.** The step is URL state; the values are
`useState`. Driven: typed `LANE5-PROBE`, type `meter`, service `water`, Continue, unit `kgal`,
manufacturer `Badger Meter`, Continue — URL `…&step=3` — then reloaded. The URL came back `step=3`,
the page rendered step 3, and step 1 showed `asset_no ""`, `type ""`, `service ""`. **Every value
gone, no banner, no alert, nothing on screen saying so.** `DEF-MET-4983`. It matters for
`AST-B-28`: a resume that pushes `?step=N` inherits exactly this disagreement.

---

## 8 · Screen 33 — Drafts, and screens 24–26 — the retire wizard

### AST-B-28 — Save as draft saves a draft

**Status: the blueprint's build plan is right and its rationale sentence is wrong.**

⚠ **THERE IS NO BUTTON. Neither asset wizard has a draft exit, a `Save & exit`, or a `Park`, on any
step.** Driven, every step of both:

```
ADD     step 1        Continue
        steps 2, 3    Back · Continue
        step 4        Back · Add asset ✓
RETIRE  step 1        Continue
        step 2        Back · Continue
        step 3        Back · Retire BAT-0904 ✓
```

The mechanism is hard-won law 2's first form: `WizardFrame` declares an optional `exit` prop and
renders `WizardExitControls` only when it is passed (`WizardFrame.tsx:851`). **`AssetAddWizard.tsx`
and `AssetRetireWizard.tsx` pass no `exit`.** So `AST-B-28`'s *"The button was drawn and saved
nothing, which is worse than no button: it is a promise the product does not keep"* is true of the
five customers wizards and **false here** — the blueprint's own *"What it takes to build"* row gets
it right (*"which neither passes today"*), so the document contradicts itself and the build row wins.
There is no registry **Drafts** control either: checked on all seven tabs, zero matches for *draft*.

### The five wizards to copy from, found and named

`WIZARD_PARK_FLOWS` is `("move_in","move_out","transfer","disconnect","new_connect")`
(`apps/tenancy/models.py:1717`, with a CHECK constraint `ck_wizard_parks_flow` at :1825), and the
port is `apps/tenancy/wizard_parks.py`. Six front-end files pass `exit`:

| file | `onSaveAndExit` | Park |
|---|---|---|
| `customers/NewConnectWizard.tsx:603` | bare `navigate("/accounts")` | **live** — `parkStoreBlockedReason(translate)` returns null |
| `customers/MoveInWizard.tsx:585` | bare `navigate(…)` | live |
| `customers/MoveOutWizard.tsx:516` | bare `navigate(…)` | live |
| `customers/TransferWizard.tsx:408` | bare `navigate(…)` | live |
| `customers/DisconnectWizard.tsx:389` | bare `navigate(…)` | live |
| `billing/BillRunWizard.tsx:1135` | bare `navigate(…)` | **blocked** — `parkBlockedReason: t("billing.run.park.notAvailable")` |

So **five** park and the sixth deliberately does not — the blueprint's count is right, and its claim
that *"all six of its consumers are a bare `navigate(…)`"* is right too, verified line by line.

**The working pattern to copy, named for step 2:**

* `customers/wizardPark.ts` — `useWizardPark()`, `wizardParkStorePort()`, `parkedHomePath()`,
  `hydrateForm()` (rehydrates a form from the parked blob), `clampToSteps()`, `PARKED_PARAM`.
* `customers/wizardParkEndpoints.ts` — the park / read / discard calls, flow-agnostic.
* `customers/parkedDrafts.tsx` (501 lines) — `ParkedDraftsPanel`, `resumePath()`, `stepOf()`,
  `flowLabel()`, `parkedDraftsQueryKey()`. **Read its §1 before choosing a home**: it records why a
  draft is a pinned panel above the list and not extra rows inside the table — a draft shares no
  column with a real row, and folding it in would lie in `totalRows` and break server paging. The
  blueprint proposes a **Drafts** control in the registry header opening its own list, which is the
  same conclusion by a different route; the reasoning is already written down.
* `parkedDrafts.dom.test.tsx`, plus `10-scripts/render-checks/cr035-park-clickthrough.mjs` and
  `cr035-resume-clickthrough.mjs` — two clickthrough proofs step 2 can clone rather than invent.

### AST-B-28's one open decision this lane can answer cheaply

The blueprint says `waiting_on` is *"free text with a not-empty check"*, so a plain draft writes the
constant `draft`. Confirmed against the model. **`WIZARD_PARK_FLOWS` is a tuple used by a database
CHECK constraint**, so adding `add_asset` and `retire_asset` is a **migration**, not just a tuple
edit — the blueprint's *"One tuple grows by two … no new table, no migration"* is right about
`assets` and wrong about `wizard_parks`. Cheap, but it is a migration and it is on a
🔒 sensitive path (migration ordering).

---

## 9 · AST-B-27 — the columns nothing can write, PROVED at the row rather than argued

**Status: confirmed, sharpened, and the decision it waits on is bigger than "which step".**

`_validate_asset` (`apps/assets/services.py:635-700`) accepts all eight on create **and** update —
`external_ref`, `form_class`, `seal_no`, `location_note`, `allocation_rule`, `loss_tolerance_pct`,
`depreciation_method`, `allocation_share_pct` — exactly as the blueprint says. No schema change and
no endpoint change is needed.

**Proved by creating a sub-meter through the wizard end to end** (`LANE5-SUB-1`, parent `M-7001`,
service `water`, unit `kgal`), then reading it back from the API and from the database:

```
SUB specs  = { form_class: null, register_digits: 9, firmware_version: null, seal_no: null,
               warranty_end: null, last_test_date: null, test_interval_months: null,
               location_note: null, allocation_rule: null, loss_tolerance_pct: null,
               allocation_share_pct: null }
SUB valuation = { …, depreciation_method: null, … }
SUB external_ref = null
```
and straight from PostgreSQL, all three assets this lane created:

```
 asset_no          | sp_null | alloc_share | alloc_rule | loss_tol | seal | loc_note | ext_ref | form | depr
 LANE5-ASSIGNED-2  |    f    |             |            |          |      |          |         |      |
 LANE5-MASTER-1    |    t    |             |            |          |      |          |         |      |
 LANE5-SUB-1       |    t    |             |            |          |      |          |         |      |
```

**Eight NULLs, eight columns, three assets, and not one of them was asked for on any of the four
steps.** The sub-meter's detail page then renders the words **"Allocation share"** as a label — a
reader over a column with no writer — and its header controls are **Assign** and **Delete** only:
**there is no Edit control on a sub-meter detail page at all**, so the edit dialog the blueprint
offers as the alternative writer is not reachable from the asset. The only writer for
`allocation_share_pct` anywhere in the product is the import runner
(`apps/metering/import_runs.py:2057, 7843`), which is out of scope for this CR.

### ⚠ The decision — identified, NOT made

The blueprint's section-06 table files **all three** allocation columns under *"Sub-meter only"* and
says *"the three allocation rows appear on the sub-meter variant only"*. **Two of the three are not
the sub-meter's.**

* `apps/assets/models.py:371` comments the pair exactly: *"Master-meter reconciliation config
  (US-MET-003 §5 — **lives on the master asset**)"*, immediately above `allocation_rule` and
  `loss_tolerance_pct`.
* `apps/metering/submeter_reconciliation.py:252` reads `tolerance_pct=getattr(master,
  "loss_tolerance_pct", None)` — off the **master** — and its docstring cites `BR-MET-025`'s
  precedence: *"the master asset's `loss_tolerance_pct` beats the tenant/service `mismatch_pct`"*.
* `allocation_share_pct` (`models.py:365-370`) is the sub-meter's own share; NULL means *"metered,
  not allocated"* and never 0.

So the question `AST-B-27` waits on has **two parts, and the first is the one the blueprint gets
wrong**:

1. **Which VARIANT** carries each of the three? On the evidence above, `allocation_rule` and
   `loss_tolerance_pct` belong on the **meters** variant (a master), and only
   `allocation_share_pct` on the **sub-meters** variant. Putting the tolerance on the sub-meter form
   would give a clerk a field the reconciliation engine never reads.
2. **Which STEP** carries each of the eight? The blueprint marks five of them on a step
   (`external_ref` 1, `form_class` and `seal_no` 2, `location_note` 3, `depreciation_method` 4) and
   **places none of the three allocation columns on any step at all** — there is no sub-meter step-2
   wireframe in section 06.

**A third part nobody has raised:** `allocation_rule` is a `TextField` whose values the model
comments as `rubs | sqft | equal | absorb`. **No lookup table and no ratified list exists**, so a
picker for it needs a ruling of the same kind `depreciation_method` needs. Two of the eight fields
are not "add a `TextField`".

**This lane makes none of these calls.** They are recorded here so step 2 can put them, in plain
English with a worked example, to whoever rules them.

---

## 10 · AST-B-13 (R12) and AST-B-26 (helper length) — measured on my screens only

**Lane 3 owns the module-wide measurement. This section exists so step 2 has the wizard's own
numbers and does not re-measure; nothing here is filed, and no row of mine cites a helper-length
budget.** (Per the coordinator: a *"six to eight words"* convention is **not in B14** — rule 33's cap
is on refusal sentences, five or six words — so the counts below are stated as counts, not as
breaches of a rule that does not exist.)

Measured with `getComputedStyle` and DOM order, at 1440 and again at 1280, over both variants:

| | meters variant | behind-the-meter variant | both |
|---|---|---|---|
| labelled fields | 22 | 18 | 40 |
| carrying a helper | 13 | 11 | 24 |
| rendering `label → helper → input` | **13 of 13** | **11 of 11** | **24 of 24** |
| label→input gap **5px** (no helper) | 9 | 7 | 16 |
| label→input gap **29px** (one-line helper) | 9 | 9 | 18 |
| label→input gap **47px** (helper wraps) | 4 | 2 | 6 |
| helpers over ten words | 10 of 13 | 7 of 11 | 17 of 24 |

**So on this wizard the R12 breach is not "ten of eighteen" — it is every single field that has a
helper.** The rhythm holds at exactly 5px on the sixteen fields with nothing between the label and
the box, which is the blueprint's own observation ("the rhythm holds only where there is nothing to
get wrong") stated as a rate rather than a sample.

The longest string in the module is on **my** screen: `size_class` on step 2, **36 words** —
*"The size of the service connection this meter sits on. A rate ladder that prices by size uses it,
so a wrong one changes the bill. Leave it blank if you do not know it yet."* Three facts in one
helper, and the same column's helper on the device variant is **6 words** (*"Size of the equipment
standing here."*). One column, two helpers, six times the length.

**Two things to hand lane 3 that are on my screens and not in its count:**

* **Eight `input[type=date]` in this wizard, none with `min` and none with `max`** — `install_date`,
  `purchase_date`, `warranty_end`, `certification_due`, on both variants. The blueprint's J4 row
  counted five date inputs on screens 21 and 22; these are four more per variant, on four screens it
  marked *not walked*. B14 rule 7.
* **`h1` is 32px on every step of this wizard at both widths** — corroborating `DEF-SHL-4947`
  (filed by lane 6), which owns the two-sizes finding. Not re-filed.

---

## 11 · Layout at the two widths the audience uses

Clerk and utility-admin, laptop and desktop. Measured at **1440** and **1280**:

* `document.scrollWidth === document.clientWidth` on **every step of both variants at both widths**
  — `1440/1440` and `1280/1280`. **No horizontal scroll anywhere.**
* The field list, the DOM order and every label→input gap are **identical** at 1280 and 1440. The
  form is capped at `max-w-4xl` (896px), below both, so nothing reflows.
* The `grid-cols-2` / `grid-cols-3` rows carry `max-md:grid-cols-1`, which never fires at these
  widths. Nothing was checked below 1280 and nothing needed to be.

---

## 12 · Where this lane disagrees with the blueprint

1. **`AST-B-14`'s carry-over table.** *"Opening read — the field: UNCHANGED … the same field in the
   same place"*, *"moved 0"*, *"Screens 29"*. It is on **step 3**. The remedy is a move plus an
   enable, and the 9→11 field arithmetic under Figure 55 describes a step-2 list the product does
   not have.
2. **`AST-B-28`'s rationale sentence.** *"The button was drawn and saved nothing … worse than no
   button"*. For both asset wizards there is **no button at all**; the document's own build row says
   so and the two disagree.
3. **`AST-B-27`'s allocation rows.** All three are filed under *"Sub-meter only"*. `allocation_rule`
   and `loss_tolerance_pct` are the **master's**, by the model's own comment and by the
   reconciliation engine's read.
4. **`AST-B-28`'s *"no migration"*.** True of `assets`; **false of `wizard_parks`**, whose `flow`
   values are a database CHECK constraint.
5. **The section-06 intro's ten-column table undercounts by one.** `model` is a ninth column with a
   reader and no writer **on the behind-the-meter variant**, which the blueprint says in prose under
   screen 29 and does not carry into the table.
6. **The five-step rail.** Correct as a remedy, and Figures 43–49 read as as-built drawings because
   every other detail in them is. The product has four steps.
7. **What the blueprint got RIGHT and this lane checked hardest:** the J5 Continue-on-empty
   correction (right, and not over-corrected); *"all six consumers are a bare `navigate`"* (right,
   line by line); `offersConnectionSize`'s three-way branch (right, and now walked); the
   `AnyTenantRole` correction (right, and there is a second copy of the false claim it missed); and
   *"no screen in the product can ever allocate it"* (right, and now proved on a row that exists).

---

## 13 · Defect rows filed by this lane

| id | what | severity |
|---|---|---|
| `DEF-MET-4980` | **AST-B-03** — the utility service is a free-text box; `GET /settings/services` is never called, though the registry one click away already calls it and 25 files do | high |
| `DEF-MET-4981` | the wizard does not mark **Service** required and the server does — 422 `assets.service_required` lands on step 4 | medium |
| `DEF-MET-4982` | a second file, **the one a lane would edit**, carries the false *"`/settings/services` is System-Admin-only"* claim | medium |
| `DEF-MET-4983` | reloading mid-wizard keeps the step in the URL and discards every answer; `?step=` out of range is clamped for rendering and never rewritten | medium |
| `DEF-MET-4984` | **Opening read** is `readOnly`, not disabled, and is pixel-identical to every editable field beside it | low |
| `DEF-MET-4985` | the behind-the-meter spec step draws every device field for every device type, and two helpers name a device that is not on screen | low |
| `DEF-MET-4986` | **the utility service required on step 1 is discarded on the default path** — an asset left in inventory keeps no service at all | high |

⚠ **These seven were allocated TWICE, and the second allocation is the one above.** The first run
took `DEF-MET-4953`–`4967`; between allocating them and pushing, lanes 1 and 2 pushed rows on the
same numbers — `4953` is now lane 1's `AST-B-01` and `4966` is lane 2's work-order door. Every
lane's arithmetic was right; what was wrong is the world the maximum came from, because a sibling in
its own worktree has no rows in the remote until it pushes (CLAUDE.md law 11). The ids were
re-derived at push time through `file_defect.py`, which caught one further race mid-run and said so,
and the three stale cross-references INSIDE the rows' own text were rewritten byte-wise with the
register's prefix proved unchanged. **No row of another lane was read, rewritten or re-serialised.**

**Not filed, deliberately:** `AST-B-14`, `AST-B-27` and `AST-B-28` are classified **changes** by
`CR-092-BRC01` §1 and become stories, not defect rows. `AST-B-13` and `AST-B-26` are lane 3's.
`DEF-3300` (the unfiltered connection-size picker) and `DEF-SHL-4947` (two `h1` sizes) are already
open and are corroborated above rather than re-filed.

---

## 14 · What this lane could NOT check, with the reason and the number

1. **The duplicate-serial warning path** (`assets.add.duplicateSerial`, `BR-AST-033`'s warn-but-allow).
   Three assets were created, none with a serial that collides. **1 string unverified.**
2. **The raise-a-work-order pre-tick.** Never ticked, so `raiseWorkOrderPath(created.id)` was not
   followed. The blueprint's J4 opened `/assets/{id}/work-orders/new` directly and it rendered with
   badge `WRK-24`. **1 control unverified.**
3. **The commit-failure panel's *Download error report*.** It rendered on both refusals and was not
   clicked; `AST-B-20` (*Download saves `file.json` containing a 404*) is another lane's row and this
   is the same control on my screen. **1 control unverified, cross-referenced.**
4. **The retire wizard's steps 2 and 3 as FIELD surfaces.** All three steps were walked for their
   **buttons**, which is all `AST-B-28` needs; screens 25 and 26 belong to whoever owns retire.
   **2 screens read for one property only.**
5. **Ten of the eleven catalogues.** Every word count above is `en.json`. B14 rule 35 says a
   catalogue is written in its own language, so the other ten may differ. **10 catalogues unread.**
6. **`?class=devices` renders the METERS wizard silently** — `classFromParam` falls back for any
   unknown class, which `BR-SHL-011`'s spirit makes deliberate and the file documents. Recorded as
   an observation, **not filed**, because it is ruled behaviour; noted here because it cost this
   lane one wrong reading before it was checked, and will cost the next one the same.
7. **Nothing below 1280.** The audience is laptop and desktop (PO 2026-09-10) and the CR says
   1280 and 1440 and nothing narrower.

---

## Trace

* **Source:** blueprint artifact `2f979496`, section 06 (lines 2447–2754), section 07 (2755–2822),
  and the `AST-B-03 / -13 / -14 / -26 / -27 / -28` cards.
* **Files read:** `AssetAddWizard.tsx` · `AssetRetireWizard.tsx` · `AssetRegistryPage.tsx` ·
  `assetsShared.tsx` · `components/WizardFrame.tsx` · `components/FormModal.tsx` ·
  `customers/parkedDrafts.tsx` · `customers/wizardPark.ts` · `apps/assets/services.py` ·
  `apps/assets/models.py` · `apps/assets/selectors.py` · `apps/tenancy/api.py` ·
  `apps/tenancy/models.py` · `apps/metering/submeter_reconciliation.py`.
* **Driven:** own stack, PostgreSQL 16 + Django `:8451` + `server.mjs` `:8452`, Chromium at 1440 and
  1280, tenant `brazosbend`, five driver scripts in this session's scratchpad.
* **Process:** `12-governance/13-change-process.md` · `12-engineering-plan.md` Addendum r11 ·
  `12-governance/22-product-maintenance-process.md`.

---
---

# STEP 2 — WHAT WAS BUILT, 2026-09-12, `2.237.3`, commit `eef41fb75`

**Appended rather than rewritten.** Everything above is step 1's reading of the
product at `2.237.0` and it stays exactly as it was filed; this section says what
moved and, where step 1 was wrong, says so by name.

## The eight rows

| id | verdict | what shipped |
|---|---|---|
| `DEF-MET-4980` | **fixed** | `SelectField` over `GET /settings/services`, filtered to `enabled`. `brazosbend` offers **two of eleven** — *Electric*, *Water*. Zero hardcoded service codes remain, as step 1 asked |
| `DEF-MET-4981` | **fixed** | `requiresService(klass)` mirrors `_check_measuring_requirements`; `stepValid(1)` reads it; the label carries the marker and the control `aria-required` |
| `DEF-MET-4982` | **fixed** | both false *"System-Admin-only"* sentences corrected, in `AssetAddWizard.tsx`'s footer and `AssetRegistryPage.tsx`'s, plus the hedged third at `:303` |
| `DEF-MET-4983` | **fixed** | a `?step=` past the first, over an **untouched** form, is not honoured: the address is rewritten to `step=1` and a `role="status"` note says why |
| `DEF-MET-4984` | **fixed** | `disabled` rather than `readOnly`, rendering in `buttonKit`'s own refused spelling |
| `DEF-MET-4985` | **fixed** | the two helpers WIDENED to the drawing's own sentences |
| `DEF-MET-4986` | **partially-fixed** | the screen states the consequence; the storage question is `OQ-MET-1768`, OPEN |
| `DEF-MET-4990` | **fixed** | filed by this lane: the step-4 summary printed lookup codes |

## Four things step 1 could not have known, and one it got wrong

1. ⚠ **THE BLUEPRINT PDF SETTLES `AST-B-14`, AND STEP 1's READING OF WHERE THE
   DRAWING PUTS THE OPENING READ WAS REPEATED TO THE PO AS A FALSE QUESTION.**
   Step 1 §12 says the drawing has the field on step 2 and the CODE has it on
   step 3 — **both halves are right**, and the coordinator's own briefing
   inverted it. PDF page 114 draws *Opening read* on **step 2**, enabled, marked
   NEW; page 117 draws step 3 with **no** opening read at all. The PO then ruled
   (2026-09-12): ***"a) Build it as drawn — move it to step 2, beside the
   multiplier, register digits and the warning"***, and the decision log puts
   that in **wave C**, *"cannot start until wave B lane 5 lands"*. **So this lane
   deliberately left the field where it is and made the refusal look like one.**
   `AssetAddWizard.tsx` carries the instruction for wave C at the control itself:
   delete it from `AssignmentStep`, do not merely drop the `disabled` prop.
2. **`DEF-MET-4985` DID NOT NEED THE BRANCH STEP 1 IMPLIED.** PDF page 115 —
   the backflow-preventer variant — already carries *"The meter that measures
   it."* and *"A capacity, never money."*: one sentence per field, true of every
   device. A `deviceExports()` predicate was written, proved unnecessary against
   the drawing and deleted. The FIELDS are untouched, because which device types
   may record an export capacity is ruled nowhere.
3. **THE DRAWN HELP SAYS *"One of the tenant's enabled services."* AND SHIPPED AS
   *"One of your utility's enabled services."*** `tenant` is our word. One
   deliberate divergence, filed here per the skill's §4 rather than followed.
4. **THE DRAWN LABEL IS *Utility service*, NOT *Service*, AND IT COULD NOT BE A
   RENAME.** `assets.form.service` is also rendered by
   `features/ledger/CostOfServicePage.tsx:430`; one screen's drawing may not
   relabel another screen's field. A new key `assets.form.utilityService` carries
   the drawn word, in eleven languages.
5. **STEP 1's §2 BASELINE RE-CHECK IS STILL SOUND** — every as-built statement it
   makes about this wizard held at `ce623f444` and the fixes are measured against
   exactly those bytes.

## `DEF-MET-4986` PROVED AGAIN, ON THE ROW, AFTER THE FIX

The PO's ruling *"you can do actual figures"* let this lane seed. **Four meters
were created through the FIXED wizard**, each with **Water** chosen on step 1 and
step 3 left on its default *Into inventory* — `LANE5B-INV-1440`,
`LANE5B-INV-1280`, `LANE5B-INV-1440-055308`, `LANE5B-INV-1280-055308` (two more
per subsequent run of the walkthrough, which suffixes the number). Read straight
out of PostgreSQL with `app.tenant_id` set:

```
 asset_no                   type    service_point_id  service  stage      unit
 LANE5B-INV-1280            meter   None              None     inventory  kgal
 LANE5B-INV-1280-055308     meter   None              None     inventory  kgal
 LANE5B-INV-1440            meter   None              None     inventory  kgal
 LANE5B-INV-1440-055308     meter   None              None     inventory  kgal
```

**The service is still discarded.** What changed is that the screen says so
first. `brazosbend` now holds **18 assets** (14 before this lane).

⚠ **ONE MORE SEED, NAMED SO NOBODY MISTAKES IT FOR FIXTURE:**
`lane5@brazosbendutilities.com`, a System-Admin member of `brazosbend` with the
demo password. `dana@brazosbendutilities.com` was LOCKED
(`locked_until 2026-09-12T05:51:46Z`) when this walk started, by a sibling's
failed sign-ins; clearing that reaches into an account other lanes are using and
minting one does not.

## How this was proved, and where the proof lives

* **13 dom cases** — `07-frontend/src/features/assets/AssetAddWizardFixes.dom.test.tsx`.
  **Eleven RED** against `ce623f444`, and then **each RED a second time
  individually** with only its own fix sabotaged, because a whole-change revert
  kills most cases on *"Unable to find a label"* rather than on their own
  assertion. Two cases are declared as NON-DISCRIMINATING in the file itself.
* **3 backend cases** — `06-backend/tests/test_def_met_4986_inventory_service.py`,
  the first proved red as `assert None == 'water'`. It PINS today's behaviour and
  names `OQ-MET-1768`, so whichever way the question goes the test fails and says
  which question it is about.
* **32 browser checks at 1440 and 1280** —
  `10-scripts/cr092_lane5_add_asset_walkthrough.mjs`, all passing, re-runnable
  (the asset numbers carry a per-run suffix because a duplicate number is
  `BR-AST-033`'s hard block and a walkthrough that passes once is one nobody
  re-runs).
* `AssetSizeDoors.dom.test.tsx` now **drives from step 1** instead of mounting at
  `?step=2`. ⚠ **This was not tidying.** `DEF-MET-4983`'s redirect would have
  parked all five of its cases on step 1, and **TC-D3 and TC-D11 assert an
  ABSENCE** — they would have gone on passing while looking at the wrong screen.
  TC-D3 was shown RED on the new harness (the meters-only guard deleted) before
  the harness was trusted.

## Two reds found that are NOT this lane's, filed rather than fixed

* **`DEF-MET-4993`** — `routeBUtilities.test.ts` has been RED since
  **2026-09-09** (`c724ab25a`, `2.234.15`) over a bare `rounded` in
  `UnitDetailPage.tsx:1337`, which compiles to nothing because `tailwind.css`
  clears the `--radius-*` namespace. Dated with `git log -S`, present at
  `ce623f444` and at the tip. Another module's live screen; giving it a radius is
  a visible change that belongs to its owner.
* **`DEF-GOV-4992`** — `allocate.py --verify` answered *"TAKEN — a sibling pushed
  it"* for `4990` immediately after **this lane** pushed a commit whose CODE
  COMMENTS cite `DEF-MET-4990`. No register on any branch holds such a row, and
  `file_defect.py` — which reads rows rather than citations — allocated 4990 in
  the same minute. The docstring's *"your own row does not count against you"*
  excludes only the working tree.

## What this lane did NOT touch, and why

`AST-B-14` (wave C, ruled) · `AST-B-27` · `AST-B-28` · the four shared-table rows
(their own CR, PO ruling 7) · the Imports tab and `AssetImportWorkflow.tsx` ·
`DEF-3300` (the unfiltered connection-size picker) · `DEF-SHL-4947` (two `h1`
sizes) · the *"Into inventory" / "Assign to a unit"* wording and order, which the
remedy drawing changes to *"To a unit" / "Leave it in inventory"* and which is
nobody's row yet.
