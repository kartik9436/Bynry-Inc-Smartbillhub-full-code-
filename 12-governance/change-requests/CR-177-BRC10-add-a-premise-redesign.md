# CR-177-BRC10 — Add a premise, redesigned: one Address section, Check address, the same-address prompt, Owner by search and link, Property · Units · Review

**Raised:** 2026-10-09 by the Product Owner, in chat (decision log rows of 2026-10-09 that start *"PO GO — BUILD THE ADD-A-PREMISE REDESIGN"*, *"PO RULINGS — ADD-A-PREMISE REDESIGN, CONTINUED"* and *"PO RULING — THE ADD PREMISES 'ONE PREMISE' FLOW (PRM-07) IS REDESIGNED"*).
**Status:** **BUILT — 2.565.0** (round A `d546029aa` server · round B `bbf0412a1` screen · round C `24127b4f4` proof · round D release). `DEF-MET-10034` closed fixed. Rollback: redeploy 2.564.0 (CHANGELOG).
**Branch:** `claude/charming-pascal-k7i2lr` (`BRC10`). `10-scripts/allocate.py cr` answered **176**, which the Add units lane (`CR-176-BRC10`) pushed first while this lane worked; re-asked it answered **177**, and `--verify 177` reported it free on every branch; suffix `BRC10` is this branch's (claimed by the `CR-156-BRC10` row of `14-id-reservations.md`).
**Classification (`13-change-process.md` §1):** a **CHANGE** with a **DEFECT** inside it. A clerk can add a premise today, so this is MAINTENANCE (`22-product-maintenance-process.md`) borrowing Build's drawing step — a live screen redrawn end to end. The PO asked for the screen to change and approved the drawing, so the redesign is a change; the four bugs the PO saw on the old screen are `DEF-MET-10034` (search on every keystroke at a utility with no City map, map fields shown with no City map, `3721 S Village Dr,, Avenel`, a required custom field skipped). `DEF-MET-10035` (Units list / Add units) is a SEPARATE defect and is not built here.

## 0 · What arrived, in the requester's words (verbatim)

| | The PO, verbatim |
|---|---|
| The go | *"can you start all tasks as per these - any changes - please add it"* |
| One section | *"keep thme in same section"* · *"instead of premises - call it address"* · *"keep in in 1 line ineatsd of 2"* |
| Dropdowns, names | *"City limits - make this drop down; Services - also multi seelct drop down - active services for that utility; Reading & billing - headline should change to area and sub area; Your own fields - call it custom field - and make it collasable; and also proide link for custom field in settings"* |
| Check address | *"below this address - we need a button to check address validdity - uisng gis api or city map … if integration is done for that tenant - then address matches then it will shwo the detials otherwise it will show that this integration not available and adderss cannjot be validated"* |
| No How many step | *"our mistake please remove how many step … there is seperate improt fucntion for premsies bulk import so step 1 how many not required"* |
| Same address | *"when address is added, we need to check for uniquness, exact same address if existing in system then you should promp user that eact same address is available"* |
| Owner | *"in owner - allow to search amster account from master account list. if it is found then shwo the details, if it is not foudn then show this account not available; anyway woner is options - and we shoudl allow to move forward"* · *"instead of chnge - it should be link or use this. you should nothave these field - Account type … Person or company … Managed by - it will come as part of account seach"* |

## 1 · The drawing

Fourteen images at 1440 wide, taken from the approved mock-up (v11), are committed beside the other redesign drawings: `05-prototype/add-premise-2026-10-09/images/01..14-*.png`, with the mock-up as `add-premise-mockup.html` and the index in its `README.md`. The mock-up's own colours and fonts are not our style: B14 rule 44 — the drawing gives the shape, our kit, tokens and spacing build it. The example data in the drawing (`P-00086`, Avenel NJ, Bramble Property Group, Roof age) is illustration only (B14 rule 37).

## 2 · Round A — the server (built)

| Task | What now happens | Where |
|---|---|---|
| 1 · same address | `GET /premises/same-address` answers the existing premise (number, address, units, status) for an EXACT match on street, city, state and ZIP, ignoring capitals, spaces and punctuation, scoped to the utility. `POST /premises` (and the City's door, which delegates with the same screen) refuses the same address with *"This address already exists."* naming the premise, unless the request says `add_anyway: true`. Imports, the sample seed and New Connection are not refused here. | `metering/address_match.py` (`exact_address_key`, `premises_with_same_address`), `metering/services.py` (`same_address_refusal`), `metering/api.py` |
| 1b · owner search | `GET /premises/owner-search?q=` pages (NFR-3, no cap) the utility's MASTER accounts whose number, customer number or holder's name contains `q`: account number, name, account type, person or company, managed by, status. Customers answers the account half through metering's read-only seam; *Managed by* is the `owner_manager` recorded on the properties that account already owns. | `customers/selectors.py`, `metering/seams.py`, `metering/selectors.py`, `metering/api.py` |
| 2 · Check address | `POST /integrations/gis_esri/check-address` asks the City ONCE: `match` (the City's address, parcel, point) · `no_match` · `not_connected` (no City map; nothing dialled) · `unavailable` (a City map that could not answer, with its reason). | `integrations/gis.py` (`check_address`), `integrations/api.py` |
| 3 · Use these details | Already built behind `POST /integrations/gis_esri/premises`: with the parcel and point the City is re-checked at the save and its address, parcel, point and *checked* stamp are written. Proved by test. | `integrations/gis.py`, `integrations/seams/metering.py` |
| 4 · required custom fields | Already enforced on `S16` by tenancy's validator (`customFields.required` on `custom_data.<key>`); proved by test for both a blank and an absent answer. | `tenancy/custom_fields.py` |
| 5 · no double comma | `compose_address` trims spaces AND commas from every part and skips an empty one; the screen's `composeAddress` is the same rule. | `metering/services.py` |
| 10b (server) · no account from this screen | From Add a premise the six keys that opened an owner account (`owner_account_type`, `owner_kind`, `owner_ssn`, `owner_driving_licence`, `owner_phone`, `owner_tax_id`) are refused by name, and the owner-account door runs only when the clerk linked an account. New Connection and the import still open accounts exactly as before. | `metering/services.py` |

**Proof:** `06-backend/tests/test_cr177_add_premise_redesign.py` — 28 passed on SQLite and **28 passed on PostgreSQL 16** (`--ds=config.settings.pgtest`). The duplicate cases were shown RED first (`DID NOT RAISE BizError` with the check switched off). No real City is dialled: every City in the file is a recorded `.example` host.

## 3 · Round B — the screen (built)

`07-frontend/src/features/metering/addPremise/` — `AddPremisePage` (the page, the rail and the *This premise* card), `PropertyStep` (Address · Map · Owner · Area & sub-area · Custom fields), `OwnerSection`, `UnitsStep`, `ReviewStep`, `addPremiseModel` (the form, the payload, `composeAddress`), `addPremiseShared` (the closed section with its state in the header, the result box). Tailwind only, every file on `src/styles/route-b-migrated.txt`. `AddPremisesWizard.tsx` is now only the route's import.

| Task | Built |
|---|---|
| 6 | Property · Units · Review; opens on Property; no *How many?* step. |
| 7 | One *Address* section; City · State · ZIP on one line; Property type and City limits (a dropdown) side by side; Services is a multi-select of the ACTIVE services, *All services* first, none ticked. |
| 8 | *Check address* and its answers (not connected · match with *Use these details* / *Keep my address* · no match · a City that could not answer); the *Map* section only after a match. |
| 9 | *This address already exists.* naming the premise by number, with *Open P-…* / *Add it anyway*; Continue waits for a choice; the save carries `add_anyway: true`. |
| 10 / 10b | Owner, Area & sub-area and Custom fields as closed sections whose header says their state; *Manage custom fields in Settings →* opens the real page; a missing required field opens its section and marks the field. Owner is a search of master accounts with a read-only card, *Link this account*, *✓ Linked*, *Unlink*; no hand-typed owner fields. |
| 11 | Units: how many and the type; the first unit's own custom fields and its services'; *Common areas* as a closed section. |
| 12 / 13 | *Check before saving*: one table grouped Address · Property · Owner · Area & sub-area · Custom fields · Units, *Edit* on every row, *—* for empty, one outcome line (*Creates 1 premise and 1 unit.*); the *This premise* card beside every step. |
| 14 | Every explanation removed; 84 new keys in all eleven catalogues in each language's own words (one re-worded to obey rule 33); **107 keys retired** that nothing names any more. |

**Removed, with its consumers (blast radius, both ways):**

- **The four-mode wizard** (`AddPremisesWizard.tsx`'s *How many?*, *Premises CSV*, *Units pattern*, *Units CSV*). Nothing linked into the three bulk modes (`?mode=` was re-pointed to Import on 2026-08-21 and to Add units on 2026-09-09); `AddUnitsWizard` stopped importing `patternTotal`/`PATTERN_UNIT_CAP` from it in the Add units redesign the same day.
- **`FindTheAddress.tsx`** (search on every pause in typing) and its front-end helper `searchCityAddresses`. Only the old wizard mounted it; `WhereAPropertyIs.dom.test.tsx` imported two of its exports for one describe block, retired with it. The server's `GET …/address-search` stays (nothing on screen calls it).
- **The owner-account fields** (Account type, Person or company and its identifier boxes, Managed by). The old save OPENED an owner master account from them (`BR-MET-1176`, `_ensure_owner_master_account`); from this screen it now only links an existing one, and the server refuses the six opening keys by name from it. New Connection and the import still open accounts.
- **Old tests:** `AddPremisesWizard.test.tsx`, `AddPremisesWizardCityGate.dom.test.tsx`, `FindTheAddress.dom.test.tsx` and `RoutePickerStates.dom.test.tsx` deleted (their still-true cases — route states, areas, services, city limits, owner link, custom fields — are re-asserted against the new page in `AddPremisePage.dom.test.tsx` or against `addPremisePayload`); `PremisesFormSections.test.tsx` now asserts the edit form alone.

**Found and filed:** `DEF-MET-10038` — Edit premise no longer matches the redesigned Add a premise (PO 2026-09-08: the two should match). Open; it needs its own drawing step.

**Converged with the Add units lane (`CR-176-BRC10`):** Owner uses its `components/PickBySearch.tsx`; Services uses its `CheckDropdown mode="every"`. This lane's own `pickAll` option was dropped before it landed.

## 4 · Round C — the proof (built 2026-10-09)

**Tests.** `06-backend/tests/test_cr177_add_premise_redesign.py` — **29 passed on SQLite and 29 passed on PostgreSQL 16** (the duplicate check, its savepoint and the City door are the reason it is run on both). The 29th is new in this round: the walk found a comma typed at the end of the street left the REVIEW right (`compose_address` trims) and the ROW wrong — `address_line` stored `3721 S Village Dr,`, so any other screen joining the parts would print `Dr,, Avenel` again. Add a premise now stores each address part trimmed of edge commas and spaces (`create_premises`, S16 only). The test was shown red with the trim removed, then green. The page's 26 tests (`AddPremisePage.dom.test.tsx`) are Round B's.

**The browser walk** — `10-scripts/cr177_add_premise_walkthrough.mjs`, with its world in `10-scripts/cr177_add_premise_world.py` (`setup` · `clean` · `connect` · `disconnect` · `readback`): a LOCAL PostgreSQL 16, a local Django, the built SPA served by `server.mjs` on `127.0.0.1`, Brazos Bend seeded, signed in as Dana. The City map is the RECORDED `.example` host (`gis_fixtures.FAST_HOST`) switched on for states 5, 6 and 12 only. **15 of 15 checks passed**; the script fails on any request leaving the local origin and counted **0** — the product's own webfont (`tokens.css` → Google Fonts, 10 requests) is counted and printed separately. Nothing dialled the live site, a City, a payment host or the Census.

**What the database holds after the two saves** (`readback`):

| Walk | Premise | Address as stored | Services | Parcel · point | Checked | Custom | Units |
|---|---|---|---|---|---|---|---|
| no City map | P-00088 | `3721 S Village Dr` · Avenel NJ 07001 (typed with a trailing comma) | water | — | unchecked | roof_age 12 | 1 |
| City map, *Use these details* | P-00089 | `1408 Pecan St` · Brazos Bend TX 78702 (the City's, replacing the typed Austin 78701) | — | 88214 · 30.2672, −97.7431 | 2026-10-09 | roof_age 8 | 1 |

**The fourteen states, built beside drawn** — screenshots in `CR-177-BRC10-walk/`, one file per drawing image with the SAME name as `05-prototype/add-premise-2026-10-09/images/`; `results.json` holds every check. Each pair was put side by side and read. They agree on every section, its order, its header state, every button and every answer. **Where they differ, and why each is not a defect:**

- **State is a text box** (`NJ`), drawn as a dropdown (`New Jersey`). Recorded in Round B's decisions: the server stores what is typed and no state list exists to offer; a list is a separate change.
- **Unit type opens on *Choose a type*,** drawn as *Single-family home*. The drawing shows a PROPERTY type there; a unit's types are the unit tables' own five (residential … common area) and no rule maps one onto the other. Building a default would invent one (B14 rule 37: a drawn figure is an illustration).
- **The required-field line reads *This one is required.*,** drawn *Enter the roof age.* — the kit's own sentence for every custom field (B14 rule 44).
- **Roof age reads `12`, drawn `12 years`.** A number field carries no unit in Settings; the drawing's *Years* is a placeholder.
- ***Save draft & exit* is shown and refused.** Drawn; no draft store exists (Round B).

**The coordinator's Units-step question.** The *"Unit 1, Unit 2, Unit 3 are taken. Use 6"* refusal belongs to `units_pattern` on Add units (`CR-176-BRC10`). Add a premise creates a NEW premise, so none of its labels can be taken; the units go in the nested `units` list in the same transaction and never through `units_pattern`. The one clash this step CAN meet — a common area named like a unit label — is refused by the server's per-premise unique label (`BR-MET-002`) and the page routes that refusal to the Units step, on the field.
