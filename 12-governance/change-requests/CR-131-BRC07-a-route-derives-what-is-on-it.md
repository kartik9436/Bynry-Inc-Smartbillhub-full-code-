# CR-131-BRC07 — A ROUTE NAMES PREMISES AND DERIVES EVERYTHING INSIDE THEM

**Raised:** 2026-09-22 · **Branch:** `claude/laughing-thompson-kpmwih` (`BRC07`)
**Requester:** Product Owner, editing `RT-006` at Ottumwa Water Works on `v2.322.0`
**Module:** metering · **Status:** RULED AND APPROVED — *"thi sis correct"*

---

## 0 · CAPTURE

> *"next bug on route creation or edit - when user select more than 1 premises, and when there are
> many premises - and premises has 500 or 100 units all togethers and these units have 500 to 1000
> assets/meters on it, in such cases - on step 3 - it does not show list of assets- and then at
> step 4 it is not working, does not show any error nothing - user dont know what happned"*

then, having been shown the five symptoms:

> *"but what i dont understand is - routes and cycles - deriving the units, assets and accounts is
> a danalmic process - it is not status - user wil keep upaiting units, its status, add, remove
> assets, changes status of assets, move in move out accounts - in such cases when we need details
> of route or cycle - it should be deived at that time - why at this stage youa re saving or
> dealing with so many units and so many db calls - what is wrong ?"*

and the ruling:

> *"thi sis correct … route should not be status - it is dynamicallyderive the details of units,
> assets meter acocount swithin it"*

**The full ruling, the reading chosen for *"should not be status"*, the walk-order ruling and the
measurement are in `12-governance/02-decision-log.md`, 2026-09-22, *"A ROUTE IS NOT A SNAPSHOT"*.
Read that before this file.**

## 1 · CLASSIFY

**A DESIGN DEFECT, not a change request.** The product does not do what a route is for. The
requester found it as a screen that hangs; the cause is that the route stores a photograph of a
query. ⚠ **Filing this as a "change" would convert our own design error into the customer's new
requirement**, which `13-change-process.md` §1 forbids by name.

## 2 · WHAT SIGNED STATEMENT IS BEING REVERSED

**None is reversed. One is protected and one moves.**

* **`BR-MET-081` is PROTECTED, and proving it is step 1** — *"Changes take effect next read window.
  Collected reads keep their route."* Derivation is the one change that could quietly rewrite it.
* **`BR-MET-033`'s walk order DOES NOT MOVE. It stays PER PREMISES** — PO ruling 2026-09-22,
  verbatim *"a is okay"*, answering `OQ-MET-12572`. ⚠ **THIS SUPERSEDES THE PO's OWN SENTENCE OF
  THE SAME MORNING** (*"i will update the walk order on units directly"*), which was reasoning about
  `route_memberships.walk_order` — a superseded, writerless column holding **0 rows**. The
  2026-08-23 ruling *"Per premises"* is the one that is BUILT (`route_premises_orders`, both
  uniqueness rules, an audited writer, drag-to-reorder on screen, the printed sheet's stops) and it
  STANDS. A per-property order is 6 rows attached to the 6 premises this CR keeps — declared, not
  derived — so it cannot go stale, which is the September ruling's own requirement met at the
  August grain. **Steps 2 and 8 below are CANCELLED.** Decision log, 2026-09-22, *"THE THREE
  ANSWERS THAT RE-OPEN `CR-131-BRC07`"*.
* **`BR-MET-075` (a meter may be excluded and stays on the route) is UNCHANGED** — a human
  judgment, never derivable.
* **`BR-MET-074` (a conflict is a MOVE, not a refusal)** must keep working when membership is
  premises-level rather than unit-level. It is the rule most likely to break quietly.

## 3 · THE SHAPE

**Stored:** the premises on the route (6 rows) · excluded meters with their reason · the route's own
row. **Derived at read time:** units · meters · accounts. **Moved:** walk order → `units`.

**No service code, no premises count and no unit count is hard-coded anywhere.** `NFR-3` and
`NFR-5` bind this change directly: the meter list is server-paginated and no cap is introduced.

## 4 · ORDER OF WORK — AND STEP 1 IS A GATE, NOT A WARM-UP

| # | step | why here |
|---|---|---|
| **1** | **Prove a collected read keeps its route under derivation** | the one place this could rewrite a money-adjacent record. **If it cannot be proved, STOP and re-open the ruling with that fact — never work around it**. ⚠ **RUN 2026-09-22 — IT DID NOT PASS, THE PO WAS ASKED, AND ALL THREE ANSWERS ARE IN. §6 below.** |
| ~~2~~ | ~~walk order onto `units`; carry the existing values across~~ | ⚠ **CANCELLED — PO ruling 2026-09-22, *"a is okay"***. The walk order stays PER PREMISES in `route_premises_orders`, which is built, audited, printed and live. **No column is added to `units` and nothing is migrated.** The instruction is struck rather than left standing, because a cancelled step left in a plan is the stale body a lane actually reads |
| 2 | **four queries stop reading the live membership and read the COLLECTION STAMP** | PO ruling 2026-09-22, *"100"*: a route reports the readings collected on it. `DEF-MET-6143`. It is `BR-MET-081` becoming true on screen, and it must land BEFORE membership moves, so the history surfaces are already safe when it does |
| 3 | membership becomes premises-level; units, meters and accounts derived | the core. Steps 5–7 fall out of it. ⚠ **It must keep a route resolvable at COLLECTION TIME** — §6's proved hazard |
| 4 | `BR-MET-074`'s conflict-is-a-move, re-proved at premises level | the rule most likely to break silently |
| 5 | step 3's fetch — the route knows its premises, so nothing is sent | the 37,994-character URL stops existing |
| 6 | step 3's empty state — a failure says so and is never drawn as an absence | the clerk is told what happened |
| 7 | step 4's save — 6 rows, not 3,711 round trips | the hang stops existing |
| ~~8~~ | ~~walk order editable on the unit~~ | ⚠ **CANCELLED with step 2.** It is already editable, per premises, by drag-to-reorder on `RouteDetailPage.tsx` |
| 8 | retire the per-unit membership rows | only after everything reads the new shape. ⚠ **NOT DONE. MEASURED 2026-09-22 SO THE NEXT LANE INHERITS THE NUMBER RATHER THAN REDISCOVERING IT** — see §7 |

## 5 · ACCEPTANCE — IN A BROWSER, ON A PROPERTY BIG ENOUGH TO BREAK IT

⚠ **A fix proved on six units proves nothing here.** Reproduce first, at ≥ 726 units.

1. Step 3 lists the meters for 6 premises / 726 units, paginated.
2. Step 4 saves, and says so.
3. **Add a unit to one of those premises. It is on the route without anyone re-opening the wizard.**
4. Fit a meter. It is on the route.
5. Move a tenant in. The account is on the route.
6. An excluded meter stays excluded, with its reason.
7. A read collected before the change still reports against the route it was collected on.
8. ~~A reader's sheet issued last month reproduces **as issued**.~~ ⚠ **STRUCK — PO ruling
   2026-09-22, verbatim *"not required, you dont have to reproduce it . option a"*.** Nothing
   records that a sheet was printed and nothing will (`DEF-MET-6144`, closed as a deliberate
   absence). ⚠ **And a reconstruction from that day's readings is ruled out whatever else changes:**
   it shows what was READ and never what was ASKED FOR, so a stop the reader MISSED — the one thing
   anybody opens an old sheet to find — is invisible by construction.

---

## 6 · STEP 1 — THE GATE. RUN 2026-09-22 (lane R). **IT DID NOT PASS, AND NOTHING WAS BUILT.**

**The full measurement is in `12-governance/02-decision-log.md`, 2026-09-22, *"STEP 1 OF
`CR-131-BRC07` IS A GATE, AND IT DID NOT PASS"*. Re-runnable:
`10-scripts/cr131_br_met_081_gate_probe.py`.**

Moving `RT-009`'s 8 premises onto `RT-001` through `services.update_route`, on a seeded
PostgreSQL clone of the pinned tip, then rolled back:

| asked of the route | before | after |
|---|---|---|
| `meter_reads.route_id` — the `BR-MET-079` stamp | 100 | **100** |
| the delete guard | 100 | **100** |
| S25's reads list | 100 | **0** |
| read progress (`BR-MET-011`) | 100 | **0** |
| the printed route sheet | 18 meters | **0** |
| last read completion | 2026-08-12 | **None** |

* **§5 item 7 — *a read collected before the change still reports against its own route*:
  HALF TRUE, AND THE HALF THAT FAILS IS THE HALF A CLERK SEES.** The stamp is immutable and
  derivation cannot reach it. Four of the five reporting surfaces resolve the route through
  `asset__service_point__route_id`, the LIVE projection, so the reads follow the world.
  **`DEF-MET-6143`, and it is a defect of the pinned tip, not of anything this CR would build.**
* **§5 item 8 — *last month's sheet reproduces as issued*: NOT POSSIBLE AT ALL.** The sheet is
  rendered on demand from current membership and nothing records that one was printed
  (`api.route_sheet_view`: *"a clerk PRINTS the sheet; nothing writes"*). **`DEF-MET-6144`.**
  §2 forbids inventing a snapshot to make the promise true, so this is the PO's to rule.
* ⚠ **AND THE HAZARD THE GATE WAS WRITTEN FOR IS REAL AND PROVED.** The stamp's only source is
  `service_points.route_id`. A design that stops maintaining that projection stops stamping new
  reads — `collection_route_id` returns `None`, the column is nullable, **and nothing goes red.**
  Any design that lands must resolve the route at collection time THROUGH DERIVATION, not
  through a stored projection. That is now a constraint on step 3, written down.

### WHAT §4 STEPS 2–9 ARE WAITING ON

⚠ **ALL THREE ANSWERS ARRIVED ON 2026-09-22 AND NOTHING IS HELD ANY LONGER.** They are in the
decision log of that date, *"THE THREE ANSWERS THAT RE-OPEN `CR-131-BRC07`"*, verbatim:

| question | answer | what it settles |
|---|---|---|
| what does *read on this route* mean — the **100** collected on it, or the **0** on its meters today? | **PO: *"100"*** | the reporting surfaces read `meter_reads.route_id`, the collection stamp. **The cost is stated on screen:** a reading older than the stamp has no route and leaves the route filter — **0 of 516 on this fixture**, not zero on an old tenant |
| must a printed sheet reproduce as issued? | **PO: *"not required, you dont have to reproduce it . option a"*** | `DEF-MET-6144` closes as a deliberate absence. No stored sheet, **and no reconstruction presented as one** |
| walk order per property or per unit? | **PO: *"a is okay"* — PER PROPERTY** | `OQ-MET-12572` closes. **Steps 2 and 8 are cancelled**, and the September sentence is superseded by name |

**§4's symptoms 1, 2, 3 and 5 are all confirmed by reading and are UNTOUCHED** — the one
`unit_id` parameter per unit, the per-unit loop in `selectors.route_meter_picker`, the
`update_or_create` per unit, and the empty state drawn over a failed fetch. ⚠ **`getRouteMeterPicker`
has THREE callers, not one** — the wizard, `RouteDetailPage.tsx` and `RouteReadsPage.tsx` — so the
33 KB URL is built on three screens. They are real and they are not worth fixing underneath a
membership model the PO may restate once these answers are in front of them.

### ⚠ AND THE CR'S OWN TWO ESTIMATES ARE BOTH LOW — MEASURED 2026-09-22, NOT EXTRAPOLATED FROM THE CODE

`selectors.route_meter_picker` was CALLED on the seeded fixture with the query count captured
(`10-scripts/cr131_scale_measure.py`). It issues **5.1 queries per unit**, not the ~2 the §0 table
assumed, and the front end's URL costs **52 characters per unit**:

| | §0 said | measured, scaled to 726 units |
|---|---|---|
| step 3's round trips | ~1,450 | **3,711** |
| step 3's URL | ~33,000 chars | **37,994 chars** |

**Neither figure changes the diagnosis and both make it worse.** They are recorded because the §0
table is the number this CR will be quoted on, and an estimate that survives into a design decision
should be replaced by a measurement once one exists.

---

## 7 · STEPS 2–7 ARE BUILT (2026-09-22, lane R2, version 2.326.0). STEP 8 IS NOT, AND HERE IS ITS SIZE.

**The full record is `12-governance/02-decision-log.md`, 2026-09-22, *"`CR-131-BRC07` STEPS 2–7
ARE BUILT"*, with the browser walk in `10-scripts/cr131_route_wizard_walkthrough.mjs` (16 checks,
all passing, at 728 units).** §5 acceptance items 1–4, 6 and 7 are met; item 5 (a tenant moving in
reaches the route) follows from the same derivation and is covered by
`test_cr131_route_derives_what_is_on_it.py`; item 8 is struck by ruling.

| measured on a real 726-unit property | before | after |
|---|---|---|
| step 3's URL | 32,781 chars | **113** |
| step 3's cost | 3,711 round trips | **6 queries, 0.1 s** |
| step 4's save | 4,420 queries, 10.4 s | **68 queries, 0.5 s** |
| rows a route stores | 726 | **1** |
| a unit added afterwards | never on the route | **728 → 729, no wizard** |

### ⚠ STEP 8 IS NOT DONE, AND SAYING SO IS THE POINT OF THIS SECTION

`route_memberships` is **still written**, deliberately: a table is retired after its readers move,
never in the change that supersedes it. Every READ is now derived from
`route_premises_memberships`; the old rows are a legacy projection kept in step so a half-deployed
branch cannot answer two different things.

**Its blast radius, measured rather than estimated (2026-09-22):**

| where | what |
|---|---|
| `apps/metering/services.py` | **12 call sites** — the writer, the unit-move and unit-delete paths, the sibling logic, the member count on `route_dict` |
| `apps/metering/walk_order.py` | 2 |
| `apps/metering/selectors.py` | 1 |
| **tests** | **9 files** name the model, including `test_seed_demo.py`, `test_be_list_export.py` and `cr029_dynamism_fixtures.py` |

⚠ **AND ONE THING THE NEXT LANE MUST NOT ASSUME:** dropping the table also drops
`route_memberships.walk_order`, which is superseded and writerless, **and `derivation`'s
`stored_order` map is already empty**, so nothing depends on it. The order lives in
`route_premises_orders` and is unaffected. That was checked, not assumed.
