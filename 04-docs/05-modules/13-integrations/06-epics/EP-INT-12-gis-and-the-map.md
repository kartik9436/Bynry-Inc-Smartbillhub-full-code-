# EP-INT-12 — GIS: the address search, the map, and the nightly reconciliation that writes to columns that price a bill

**Module:** integrations (+ metering for the premises write, through its service) · **Wave:** phase 4–5 (`T-8`, sixteen tasks) · **Screens:** the premises create/edit address field · S141 · S143 *Waiting for a decision* tab · **Status:** `US-INT-042` **BUILT** 2026-09-06 (CR-069 wave M); `US-INT-043` draft — ⚠ **THIS LINE SAID `T-8` IS BLOCKED ON `OQ-INT-1470`, `OQ-INT-1471`, `OQ-INT-1472` UNTIL 2026-09-06, AND ALL THREE WERE RULED ON 2026-09-04** (amended 2026-09-06 by the CR-069 wave M build lane). Nothing in this epic is blocked on a question. What `US-INT-043` still waits for is wave `Q`'s home on the Runbooks side of `BR-INT-054`, which is a different fact and is not a stub.

## Scope

**In:** three operations with three different shapes on one connection — **address search** (inline, executed at the moment a clerk types, with a latency budget and a breaker, writing nothing until a person picks a row), **the map** (tiles drawn by the browser, no tenant secret, a page-security policy generated from the registered browser operations), and **the nightly reconciliation** — up to 70,000 locations, *"entire update logic is on us"* — with a per-field scope of authority, membership authority separate from content authority, seven difference classes each with a disposition, the money-path columns named in one place, and a measurement frame on every coordinate and score (`BR-INT-048`, `BR-INT-049`, `BR-INT-051`).

**Out:** the ruling on which key wins, what a clerk may do when the city is unreachable, and whether a parcel may ever become a premises by itself — `OQ-INT-1470`–`1472`, the PO's. The Census geocoder — the product's one live outbound call today, run by hand, filling only empty coordinates — moves onto the substrate as `geocoder_census` in `US-INT-013` and keeps its fill-empties-only rule (`CR-028` D6).

**Step-1 defects, not changes (`CR-069` §0.3):** the Census geocoder and the Esri tiles are live third-party calls with **no connection record, no health state and nowhere to be switched off**. Putting them on the substrate is a gap in what we built, filed as a defect row, not a new requirement.

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S143 · *Waiting for a decision* tab | premises · parcel | difference class (seven) · night · field | oldest first | night · class | premises · field · we hold · the city says · class · night seen | accept (commit) · keep ours · open premises (icons) | accept selected (same class only) · keep ours for selected | CSV of the night's report |

## Stories

---
id: US-INT-042
epic: EP-INT-12
module: integrations
screens: [S141, S142]
wave: 4
status: draft            # was `blocked`; OQ-INT-1471 ruled 2026-09-04 — type it, marked unchecked
blocked_by: []
depends_on: [US-INT-013, US-INT-019, US-INT-022]
journeys: []
rules: [BR-INT-048, BR-INT-022, BR-INT-003]
golden_tests: []
finance_calc: none
---
### US-INT-042 — Executor: our server, or the viewer's browser — the map, the inline address search with a latency budget, and a result that is offered, not loaded (C14, C15, C16) ⚠ one branch blocked

**1 · Details** — As **a clerk creating a premises**, I want **to type an address and see the city's candidates in under a second, pick one, and have the premises written from what the city holds** — so that **nothing is queued, no progress row appears, and the parcel is checked against the city at the moment I press Create, not on every keystroke**.

**`C14` — the one new dimension.** The map draws tiles from the page, hundreds per pan, and this repository configures no Content-Security-Policy at all. `executor` is declared per operation — `server`, `browser`, and `browser, credentialed` (the processor-hosted card page, PO 2026-09-03). **A browser-executed operation carries no tenant secret**; the page-security policy is **generated** from the registered browser operations; the connection card shows *the call is made by the browser* and **the test modal tests the page's reach separately from the server's**. The ruling of 22 August — *"every pan sends your asset locations to a third party"* — is generalised, not reversed: a city that runs its own map server points the same operation at the body that already owns the data (`R-7`, `C14`). **`C15` — inline completion is a latency budget, not a job:** candidates in under a second; nothing queued; when the city is slow the breaker opens and the screen says *the city's address service is not answering* rather than spinning. **`C16` — result disposition `offer`:** the candidate list is shown and **nothing is written**; a premises appears only after a person picks a row — and the parcel is **re-checked against live GIS at the moment of the write**.

⚠ **THE UNREACHABLE BRANCH WAS `OQ-INT-1471` AND IT IS RULED — OPTION (b), 2026-09-04, PO verbatim *"(b) type it, marked unchecked"*** (amended 2026-09-06 by the CR-069 wave M build lane). The question was: may a clerk still create a premises when the city cannot answer — refuse, type it in, or show what we saw last time? *"Two of the three are safe. The third writes a property against a parcel the City may have split since, and it looks identical on screen to the good case."* **The answer is the middle one, so this branch is a BUILD**: the premises is created, carries no parcel key, and is marked **unchecked** — `premises.gis_unchecked`, metering migration 0054, served by `premises_detail_dict` so the mark is visible wherever a premises is read. ⚠ **THE MARK IS THE WHOLE RULING**, because the danger the question named is precisely that the bad case looks like the good one. ⚠ **AND THIS PARAGRAPH INSTRUCTED A STUB FOR TWO DAYS AFTER THE RULING**, while §8's table beneath it said CLOSED — the prime directive's own case, corrected here rather than left for the next lane to trip over.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-048` | Executor declared; browser ops carry no secret; CSP generated; inline = latency budget + breaker; disposition `offer` writes nothing until a pick; parcel re-checked at write | PROPOSED — design §2.24.3–4; `browser, credentialed` CONFIRMED PO 2026-09-03. **BUILT 2026-09-06** (CR-069 wave M): `latency_budget_ms` and `result_disposition` are manifest data refused at load, `page_policy.py` generates the policy from the registered browser operations, and a browser operation on a provider that REQUIRES a secret is refused by name |
| `BR-INT-022` | The breaker opens on a slow provider and the screen says so | PROPOSED |
| `BR-INT-003` | No secret reaches the browser | CONFIRMED |
| `OQ-INT-1471` | Creating when the city is unreachable | ⚠ **CLOSED 2026-09-04** — *"(b) type it, marked unchecked"*: the premises IS created, marked **unchecked**, and re-checked on the next night's run. **A build, not a stub.** |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Priya types *1408 Pec* on the premises form | Candidates within **1,000 ms** (fixture 300 ms); no job row, no run row per keystroke; one `inline` run row per search session summarising *14 lookups · 1 pick* |
| TC-2 | She picks *1408 Pecan St · parcel 88214* and presses Create | The parcel is **re-checked live** at the write; the premises is written by metering's service with `external_ref = 88214`, `lat/lng` in the declared frame; nothing was written before the pick |
| TC-3 · **negative** | The city answers in 4 s three times | Breaker opens; the field reads *the city's address service is not answering*; no spinner; the S8 card shows *Not working* for that operation only |
| TC-4 · **boundary** | With the breaker open, Priya types the address by hand and presses Create | **The premises IS created** (`OQ-INT-1471` ruled (b)): `external_ref` empty, `gis_unchecked = true`, and the mark served by `premises_detail_dict` so every screen that draws a premises draws it. ⚠ **THIS CELL EXPECTED `NotImplementedError("OQ-INT-1471")` UNTIL 2026-09-06** — amended 2026-09-06 by the CR-069 wave M build lane |
| TC-5 | The map on the premises screen | Tiles requested **by the browser**; the request carries no tenant secret; the generated CSP lists exactly the registered tile host and nothing else; changing the tile host in the manifest changes the CSP |
| TC-6 | **Test it now** on the map card | Two results: *the server can reach the city* and *this page can reach the tile server* — tested separately |
| TC-7 · **tenant isolation** | Two tenants with two cities | Each search goes to its own city's service; the CSP is generated per tenant's registered hosts |
| TC-8 · **role** | **Priya is a Billing Clerk, not a System Admin** | She can search AND create from a candidate. ⚠ **ADDED 2026-09-06 (`DEF-INT-4267`) BECAUSE THE BUILD SHIPPED WITHOUT IT AND WAS WRONG:** both routes carried the *settings* permission class, whose read roles are `{system_admin, executive}` — A4's `settings_lookups` gives a clerk no cell — so the search answered `403`, the panel read that as *no City here* and removed itself, and the feature did not exist for the one role this screen is for. `metering.services.create_premises` is `@require_role(SYSTEM_ADMIN, BILLING_CLERK)`, and **a route must never be narrower than the service it delegates to.** Every case in the wave drove the service directly or through an admin fixture, so only a case that goes through the ROUTE as a clerk can hold this |
| TC-9 · **negative** | She picks a candidate whose parcel is already on another property | A refusal she can read — *Another property already has that parcel.* — never a `500`. ⚠ **ADDED 2026-09-06 (`DEF-INT-4273`).** `premises` carries `uq_premises_tenant_external_ref_ci` and the interactive path had no check and no catch, so the second pick raised `IntegrityError` through to the browser. **The nightly path had this case written down from the start** — see the reconciliation block's own TC-5, *no `IntegrityError` at 02:00* — and the interactive path, where it is far likelier, did not. Checked before the write and caught after it; the catch is outside the service's `transaction.atomic()` (law 14) |

**4 · Test Data** — `gis_city` connection for Brazos Bend: address service `https://gis.brazosbend.example/addr`, tile server `https://tiles.brazosbend.example` (city-run — R-7's case); fixture latencies 300 ms and 4,000 ms; candidate *1408 Pecan St · parcel 88214 · 30.2672, −97.7431 (EPSG:4326)*.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `executor` | S8 card · S141 | `C14` | manifest per operation | enum | reference-data | `server \| browser \| browser_credentialed` |
| generated CSP | page headers | `C14` | computed from registered browser operations | header | system-derived | exactly the registered hosts |
| `latency_budget_ms` | — | `C15` | manifest per inline operation | int | reference-data | default 1,000 |
| `result_disposition` | — | `C16` | manifest per operation | enum | reference-data | `load \| offer`; address search = `offer` |
| candidate → premises | premises form | `C16` | `premises.address_line · city · state · postal_code · external_ref · lat · lng` via metering service | text/decimal | integration → service | re-check at write; frame declared (`BR-INT-049`) |

**6 · Acceptance**
- Given a clerk types, then candidates appear in under a second and nothing is written until they pick.
- Given the city is slow, then the breaker opens and the screen says so.
- Given the map, then the browser draws it with no secret and a generated policy.

**7 · Finance Calculation** — N/A.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-INT-1471` | When the city's address service is unreachable, may a clerk still create a premises — refuse, type it in, or use what we saw last time? | The unreachable branch only | PO | ⚠ **CLOSED 2026-09-04** — *"(b) type it, marked unchecked"*. **The branch is a BUILD, not a stub:** the premises is created, marked **unchecked**, and re-checked on the next night's run, and the mark must be VISIBLE wherever the premises is read. ⚠ **This cell read `OPEN` until 2026-09-06** while the register had said CLOSED for two days — a lane briefed from here would have stubbed a branch the PO has already ruled is a build. |
| `OQ-INT-1728` | Does a record update a person makes synchronously on a screen belong to Runbooks? | This story's **Create** — the write | PO | ⚠ **CLOSED 2026-09-06 — option (a): NO.** A person's synchronous write stays with the module that owns the screen, so **this story's write stays with integrations and is a build.** ⚠ **The PO added in the same sentence that the same job must ALSO exist as a batch, in two forms — scheduled, and run once on demand.** Both batch forms run on Runbooks (the run-once TRIGGER stays on this screen; pressing a button is triggering, not scheduling). Neither is sized in this wave's four people-weeks and neither is commissioned yet. See `BR-INT-054`(5). |

---
id: US-INT-043
epic: EP-INT-12
module: integrations
screens: [S143, S142]
wave: 5
status: draft            # was `blocked`; OQ-INT-1470/1471/1472 ruled 2026-09-04 — GIS parameters are the key, unchecked is a mark, the night creates nothing
blocked_by: []
depends_on: [US-INT-042, US-INT-029, US-INT-034, US-INT-037]
journeys: []
rules: [BR-INT-049, BR-INT-051, BR-INT-024, BR-INT-029]
golden_tests: []
finance_calc: none
---
### US-INT-043 — The nightly GIS reconciliation: a per-field scope of authority, membership kept separate from content, seven difference classes, and the three columns nobody's feed may write (C17, C22–C25) 🔒

**1 · Details** — As **a utility**, I want **the city's nightly parcel file — up to 70,000 locations — checked against our premises every night, updating what may be updated by itself, queueing what a person must decide, and never touching what decides tax** — so that **a flag says which premises the city has confirmed, and the update logic is ours, written down**.

The requester's words: *"customer want nightly batch checking every day… up to 70000 locations, we have to match with our and update, entire update logic is on us."* **`C22` — scope of authority is per field: `auto`, `queue`, or `never`.** The night updates a postal code by itself, **queues** a district change for a person (S143 *Waiting for a decision*), and **never writes `inside_city_limits`, `city` or `state`** — `C25`: the columns that decide tax are named **in one place**, the refusal names the column and the reason, and the jurisdiction flag keeps having no default. The grant is **visible on screen**, not implied by code. **`C23` — membership authority is separate from content authority:** a night takes **69,000** parcels, updates the ones we have, **creates none**, and reports **66,500 not ours** as its own count — *"whether the utility serves one is a decision about the utility, not a fact the City can state"* — so a night where 2,914 matches become 300 is visible because the second number is on the report. **`C24` — seven difference classes, each with a disposition:** new-to-us · gone-from-city · field changed (auto) · field changed (queue) · money-path field changed (never) · **two of ours on one parcel key** · one of ours on two keys. The sixth is caught and **queued before** the database refuses the write at two in the morning with an error naming neither row. **`C17` — a measurement frame on every numeric** 🔒: a coordinate in a projected system is refused by name rather than written; one that fits the column and puts the pin about 700 km from the South Pole is refused too; a match score of `0.8` against a 0–100 scale is refused rather than accepting everything. The premises write goes through metering's service function; the run is `reconcile` mode (`BR-INT-029`) and its five counts are the report.

⚠ **THREE RULINGS FIRST — `T-8` does not start before them.** `OQ-INT-1470` which key wins — the utility's own `external_ref` or the city's parcel number, *"they want the same column"*: a utility loads **428** premises, re-cuts the file to fix nine postal codes, and gets **428 matches, 9 updates, 419 no-ops**; change the key and that becomes **428 new premises**. `OQ-INT-1471` the unreachable branch. `OQ-INT-1472` may a parcel in the city's records and not ours ever become a premises automatically — the proposal is **no**, it goes on a list somebody reads; about 66,500 such parcels arrive every night. To the boundary: the night runs, classifies and **reports**; every write path raises `NotImplementedError("OQ-INT-1470")`.

🔒 **Sensitive path** — a feed writing toward columns that price a bill. `HUMAN-REVIEW-PENDING`; the ledger row shows the PO the 69,000 / 66,500 / 2,914 → 300 figures and the sentence *never writes `inside_city_limits`, `city` or `state`*.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| `BR-INT-051` | Per-field `auto · queue · never`; membership separate; seven classes with dispositions; money-path columns named once | PROPOSED — design §2.26.8; 🔒; `OQ-INT-1470`–`1472` |
| `BR-INT-049` | Measurement frame on every coordinate and score | PROPOSED — `C17`; 🔒 |
| `BR-INT-024` | Nightly in the tenant's zone; skipped and recorded when still running | PROPOSED |
| `BR-INT-029` | Reconcile mode; the five counts are the report | PROPOSED |
| `CR-028` D6 | The Census geocoder fills empties only, never overwrites — unchanged | CONFIRMED — decision log 2026-08-22 |

**3 · Test Cases**

| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Night file of 69,000 parcels; we hold 2,914 premises keyed to parcels | Report: **2,914 matched · 66,086 not ours · 41 field changes auto · 3 queued · 0 created**; the *not ours* count is its own figure on S142 |
| TC-2 | A parcel whose postal code changed `78702 → 78721` | Written by itself (`auto`) through metering's service; the run's `changed` count includes it |
| TC-3 | A parcel whose district changed | **Queued** on S143 *Waiting for a decision* with *we hold · the city says*; nothing written until a person accepts |
| TC-4 · **negative · 🔒** | The feed carries `inside_city_limits = false` for a premises we hold `true` | **Never written**; the refusal names the column — *`inside_city_limits` decides tax and no feed may change it*; a row on S143 so a person sees it |
| TC-5 · **negative** | Two of our premises share parcel key `88214` in the night's file | Caught in classification, **queued** as class six, **before** any write — no `IntegrityError` at 02:00 |
| TC-6 · **negative · 🔒** | A coordinate arrives as `(3,115,214.0, 10,071,392.0)` (a projected system) | Refused by name — *coordinate is not in the declared frame* — not written; a second, `(−89.9, 0.0)` — 700 km from the South Pole — refused as out of the declared bounds |
| TC-7 · **negative · 🔒** | Match score `0.8` against a declared `0–100` scale | Refused rather than accepted as a near-perfect match |
| TC-8 · **boundary** | Any write path with `OQ-INT-1470` open | `NotImplementedError("OQ-INT-1470")`; the night still produces the report |
| TC-9 | Matches fall from 2,914 to 300 one night | Visible on the report as its own number; the S8 panel shows attention; nothing is deleted (`gone-from-city` is a class, never a delete) |
| TC-10 · **tenant isolation** | Two utilities served by one city | Each night's run classifies against its own premises; a parcel belonging to the other utility is *not ours* for this one |

**4 · Test Data** — Night file 2026-09-02: 69,000 parcels (fixture generator); Brazos Bend 2,914 premises with `external_ref = parcel`; the 428/9/419 re-import case; changed postal code `1408 Pecan St 78702 → 78721`; district change on `2210 Elm St`; `inside_city_limits` flip on `900 Riverside Dr`; duplicate key `88214` on two premises; projected coordinate and South-Pole coordinate fixtures; score `0.8`.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| per-field authority grant | S143 header · S141 | `C22` | manifest per field, overridable in `config` — **visible on screen** | enum | reference-data / user-input | `auto · queue · never`; money-path columns pinned `never` in one place |
| money-path columns | — | `C25` | `apps/integrations/seams/metering.py` — one list: `inside_city_limits`, `city`, `state` | list | code | the refusal names the column |
| difference class | S143 | `C24` | run artifact rows; queued items | enum(7) | system-derived | each with a disposition |
| *not ours* count | S142 · S143 CSV | `C23` | `integration_run.summary` + `skipped` | int | system-derived | its own figure |
| `frame` on `lat/lng` · `score` | — | `C17` | projection declares `EPSG:4326`, bounds, scale | struct | reference-data | refused by name outside it |
| confirmed-by-city flag | premises detail | requester's words | `premises.custom_data.gis_confirmed_on` via metering service — **stubbed `OQ-INT-1470`** | date | integration → service | set on a match |

**6 · Acceptance**
- Given the night file, then the report says how many matched, how many are not ours, how many changed by themselves and how many wait for a person — and creates nothing.
- Given a change to a column that decides tax, then it is never written and the refusal names the column.
- Given the rulings are open, then the night reports and writes nothing.

**7 · Finance Calculation** — N/A — no rating math here; the columns this story refuses to write are the ones that would move it.

**8 · Open Questions**

⚠ **NONE OF THESE THREE IS OPEN — ALL WERE RULED ON 2026-09-04, AND THE STATUS CELLS BELOW SAID `OPEN` UNTIL 2026-09-06.** They are corrected from the register (`OQ-INT-1470`, `1471`, `1472`, all **CLOSED**), and the frontmatter above this story has said so since the day of the rulings — **the frontmatter and the table disagreed for two days.**

⚠ **AND THE CORRECTION IS ONLY HALF DONE, DELIBERATELY: THE BODY OF THIS STORY STILL INSTRUCTS A LANE TO STUB.** `TC-8` expects `NotImplementedError("OQ-INT-1470")` on *"any write path with `OQ-INT-1470` open"*, §5's `gis_confirmed_on` row reads **stubbed `OQ-INT-1470`**, and §1's prose still says `T-8` does not start before three rulings that have already been made. **Those are not corrected here, because what to build in place of each stub is wave `Q`'s work and this lane must not choose it** (prime directive). They are named so the next lane fixes them deliberately rather than discovering them as a merge surprise. **Read the register's status column before you stub anything in this story.**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| `OQ-INT-1470` | Which key wins — the utility's own reference or the city's parcel number? (428 matches · 9 updates · 419 no-ops, or 428 new premises) | Every write of this story | PO | ⚠ **CLOSED 2026-09-04** — the GIS parameters are the key. The ruling also handed us a design job (*which* identifier is the match key), which travels to Runbooks with wave `Q` |
| `OQ-INT-1471` | May a clerk create a premises when the city is unreachable? | The unreachable branch | PO | ⚠ **CLOSED 2026-09-04** — *"(b) type it, marked unchecked"*. **A build, not a stub.** |
| `OQ-INT-1472` | May a parcel in the city's records and not ours ever become a premises automatically? (Proposal: no — a list a person reads; ~66,500 a night) | The `new-to-us` disposition | PO | ⚠ **CLOSED 2026-09-04** — **the night creates nothing.** A parcel we do not hold becomes a row on a list a person reads, never a premises by itself | OPEN |
