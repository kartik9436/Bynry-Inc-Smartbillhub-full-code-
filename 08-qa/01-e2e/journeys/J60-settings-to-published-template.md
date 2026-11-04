# J60 — Settings → a published template, and the wizard proposes it (four Settings cards stop saying *arrives with Work*, eight steps write nothing until Publish, `ST-0001` is allocated inside that one write, and New Connect step 6 proposes **5** orders and writes none)

---
id: J60
tier: 2
rules: [BR-WRK-008, BR-WRK-009, BR-WRK-010, BR-WRK-011, BR-WRK-012, BR-WRK-013, BR-WRK-014, BR-WRK-015, BR-WRK-016, BR-WRK-017, BR-WRK-018, BR-WRK-019, BR-WRK-021, BR-MET-109, BR-MET-112, BR-TEN-035, BR-SHL-025, BR-SHL-035]
stories: [US-WRK-006, US-WRK-007, US-WRK-008, US-WRK-009, US-WRK-010, US-WRK-012, US-WRK-013, US-WRK-014, US-WRK-015, US-WRK-016, US-WRK-017, US-WRK-019]
# ⚠ **NOT ACTIVATED** — there is no `J60.spec.ts`, and none could pass today: every
# story above is `wave: 1` of `CR-070` and NOTHING in `apps/work/` exists at HEAD
# (`04-docs/05-modules/16-work/01-overview.md` §7 — four Settings cards render
# *arrives with Work*, twenty-four starter rows are seeded and inert, and there is
# no template builder). This file is the HANDOFF CONTRACT the prime directive's
# dependency rule asks for — what each step leaves in the database for the next —
# written BEFORE the code so the code is built to it (the J27 precedent).
#
# `stories:` is the set of stories this journey EXERCISES, and since 2026-09-03
# (`DEF-WRK-3571`) `16-work/04-flows.md`'s index and every story's own frontmatter
# agree with it: `US-WRK-007`, `008` and `017` now cite `J60` in their frontmatter
# (steps 2, 3 and 11 exercise them), and `US-WRK-018` — the v2 publish, `J67`'s —
# was dropped from the flows index and from this list, because a first publish
# never exercises it. `US-WRK-006` (the fixture) names all eight journeys.
---

**Intent.** Phase 1 of the Work module, end to end, as `CR-070` §11 states its exit
test: *"a utility authors its own job templates, and the wizard proposes them."* Two
promises the shipped product already makes on screen are kept here — the four
Reference-data cards that say *"Field work is not part of this release yet"* start
editing real rows, and the `ST-{0000}` series that has sat on the Numbering screen
since 2026-08-16 gets a column to write into. Then a System Admin walks the eight-step
builder the Product Owner designed (`WM-11`), and the journey proves the two rules the
builder exists to keep: **nothing reaches a work order until Publish** (`BR-WRK-011`),
and **a published template is a versioned bundle of ROWS, copied onto orders, never
linked** (`BR-WRK-008`, `BR-WRK-009`). It ends where phase 1 ends — New Connect step 6
proposes work orders from the utility's OWN templates and, per `BR-MET-112`, still
writes nothing.

**What this journey is really proving:** that there is exactly ONE write in the whole
flow — Publish — and that everything before it is a draft a browser tab can lose
without loss. That is `BR-MET-112`'s shape borrowed for templates, and it is why step
5's *publish twice quickly* is the load-bearing negative.

**Upstream leaves (the fixture this journey starts from).** Tenant **Brazos Bend
Utilities** (`brazosbend`), seeded (`US-WRK-006`, phase-1 half): the **24 seeded
starters** across the services the tenant sells, marked `is_sample`, gas gated on the
**light-up** (`BR-WRK-013`); the six lookups seeded with the cards' own sample copy —
Skills *Water I–III · Electric I/II · Meter I · Reads · Excavation*, Safety kits *Basic
PPE · LOTO · Confined space · Traffic control*, Parts categories *Meters · Consumables*,
Priorities *Urgent 4 h · High 8 h · Normal 72 h · Low 168 h*, the eight r10 job types
(*Reconnect · Main repair · Disconnect · non-pay · Leak investigation · Meter exchange ·
Backflow inspection · Read verification · Move-in activation*); the parts register
holding `MTR-W58 · 92.4000` · **`MTR-E1P · 96.0000`** · **`SEAL-01 · 0.2200`** ·
**`GSKT-STD · 1.8000`** · `GAUGE-BF · 640.0000`; Numbering (`Work-019`) reading
*WORK · 4 of 27 series* with `ST-{0000}` **next 1** and `DSP-{YY}{MM}{DD}-{00}` next 1.
Actors: **Alex Reed** (System Admin) for Settings and the builder; **M. Torres**
(supervisor) for the New Connect wizard. Isolation tenant: **Lone Star Ridge WSC**
(`lone-star-ridge`), seeded with its own starters and nothing of Brazos Bend's.

**Fixture the journey adds.** Skill *Backflow*; job type *Backflow test* (default
priority Normal · default template *Backflow inspection* · 35 min · customer present:
no); the template **Meter exchange — residential** from the *Meter exchange* pack —
Electric · job type Meter exchange · applies to *Electric meter · AMI single-phase ·
Water meter 5/8"–1"* · skill Meter fitting · crew 1 · safety kit *Standard electrical* ·
**3 safety · 7 tasks (45 min) · 3 materials · 3 readings · 3 help · signature required**
= the **26 items** `Work-017` draws; a New Connect for **`12 Heron Way`**, 1 unit,
Electric + Water (`US-WRK-017`'s build, later `CON-26-0129` in `J61`). Dates: the
Settings and builder steps on **Mon 2 Mar 2026**; the wizard the same afternoon.

**Where two documents disagreed, and which one this journey follows.**
* **Template number and v1 task count.** `04-flows.md` says `J60` leaves **`ST-0001`
  with 7 tasks**; `Work-022`, `US-WRK-018` and `J67` say *Meter exchange — residential*
  is **`ST-0002`** and its **v1 had 6 tasks** (v2 added *Apply tamper seal*). This
  journey follows `04-flows.md` and the pack (7 tasks · 26 items, as `Work-017` draws
  for the PO); the number is whatever the series allocates on a tenant whose counter
  reads 1 — `ST-0001` here. `J67` starts from the SEED's v1, not from this file's
  output. **Filed as `DEF-WRK-3572`** (2026-09-03): the two run on different fixture states of one tenant and do not chain — `04-flows.md` and `US-WRK-006` §4 now say so.
* **Step 6 proposes 5, not 6.** `BR-WRK-016` says step 6 proposes *"from the enabled
  services' PUBLISHED templates"*; after this journey Electric has THREE published
  templates (two starters plus the exchange) and `US-WRK-017` TC-1 / `04-flows.md` still
  say **5**. The count is followed (the more specific document wins) and the rule's
  missing clause — the proposal draws the new-connect job type, not every published
  template of the service — is **filed as `DEF-WRK-3573`, and `BR-WRK-016` is amended** (the proposal draws the published templates that hold a place in the service's connection `sequence`, not every published template of the service); step 11 asserts the 5 and
  asserts the exchange template's ABSENCE by name so the gap cannot close quietly.

| # | Actor · action · screen | Expected outcome (contract — what this step leaves) | Downstream assertions (record · screen · audit · books) | Rule |
|---|---|---|---|---|
| 1 | **Alex Reed** opens **Settings › Configure › Reference data › Work** (`Work-018`) | The four cards — skills · safety kits · priorities & SLA · parts categories — each render a `DataTable` of real rows with ✎ and − row actions; **the sentence *arrives with Work* renders on NO card** (grep of the rendered page = 0) | The cards are `kind: "list"` reference-data config pointing at `/work/skills`, `/work/safety-kits`, `/work/priorities`, `/work/part-categories` — **data, never a new layout** (`BR-SHL-035`). A card with zero rows shows what is missing and the action that fills it (B14 rule 17), never the old sentence. Every row carries the seeded sample copy of `US-WRK-009` TC-2 | **BR-WRK-017** · BR-SHL-035 · `US-WRK-009` TC-4 |
| 2 | Alex adds skill **Backflow** to the Skills card; adds job type **Backflow test** (Normal · *Backflow inspection* · 35 min · customer present no) | One `work_skills` row (`active = true`) · one `work_order_types` row; one `audit_log` row each, actor Alex Reed | *Backflow* appears in the **Skill needed** picker on `Work-014` and in the skills wizard reached from `Work-024` on the next load; *Backflow test* is **ninth of nine** in the Type picker and in `Work-007`'s Type filter. ⛔ A second type with code `METER_EXCHANGE` is REFUSED — unique (tenant, code); sentence ≤ 6 words (B14 rule 33). ⛔ Deleting a type an order references is REFUSED and the card offers **Deactivate** instead (the shape templates use, `BR-WRK-012`) | **BR-WRK-017** · `US-WRK-007` TC-1/TC-3/TC-4 |
| 3 | Alex opens the **priorities** card and the **parts register** (`Work-025`, Stock register segment) | Priorities read Urgent 4 h · High 8 h · Normal 72 h · Low 168 h with their colour chips; parts read `MTR-E1P · Electric meter · 1φ AMI · Meters · each · $96.00`, `SEAL-01 · $0.22`, `GSKT-STD · $1.80` — **stored 4 dp, shown 2** | ⛔ SLA hours `−1` REFUSED at validate. ⛔ Unit cost `92.40004` REFUSED — more than 4 decimals (hard rule 2). ⛔ A part with no unit of measure REFUSED (hard rule 3). **`GET /work/parts` carries NO `on_hand`, `reorder_at` or `location` key — asserted by name** — and the *Reorder — 2 parts at or below reorder level* banner `Work-025` draws is **not rendered**: `parts.stock_position()` raises `NotImplementedError("OQ-WRK-1490")` and nothing calls it. The three stock columns the wireframe draws are HELD until ruled | **BR-WRK-018** · **BR-WRK-019** · hard rules 2, 3 · **OQ-WRK-1490 (boundary)** |
| 4 | Alex opens **Settings › Numbering › Work** (`Work-019`) | *WORK · 4 of 27 series*: Connection `CON-{YY}-{0000}` · Work order `WO-{0000}` · **Service template `ST-{0000}` next 1 · sample `ST-0001`** · Dispatch batch `DSP-{YY}{MM}{DD}-{00}` next 1 | **Nothing in `apps/work/` allocates from `dispatch_batch`** — a test greps for call sites and finds zero (`US-WRK-012` TC-4); the series stays on the screen exactly as seeded (PO 2026-08-16: *"it should work standalone in settings; we will link it later ith work"*). What a dispatch batch IS is **`OQ-WRK-1497`, OPEN, non-blocking** — the journey asserts the absence of an allocator, never a meaning | **BR-WRK-021** · BR-TEN-035 · **OQ-WRK-1497 (boundary)** |
| 5 | Alex opens **Work › Templates** (`Work-013`) | The list where `Work-005`'s four sentences used to be. `CountFooter` **foots**: on this fixture *6 templates · 4 published · 1 draft · 1 inactive · Seeded starters are marked and can be edited or deleted* (the drawn figures; the spec asserts published + draft + inactive = total, because the seed is service-shaped and the count follows what the tenant sells — `DEF-2397`) | **Contents** counts the bundle per row — *New connection · Electric · 2 tasks · 0 parts · 1 reading*; a starter with nothing behind it reads *0 tasks · 0 parts · 0 readings*, **never blank**. **Water holds two templates at once** (*New connection* and *Leak investigation*) — the case the old `unique(service, sequence)` forbade; the key is now `(tenant, name, version)`. Gate column: Electric *Meter set 🚩*, **Gas *Light-up 🚩*** — never Meter set. Seeded rows are marked *seeded*. Toolbar per CR-045 (search · filter set · download) even though the drawing shows the filter only | **BR-WRK-010** · **BR-WRK-013** · `US-WRK-013` TC-4/TC-6 |
| 6 | Alex presses **+ New template** → `Work-014` step 1; picks the **Meter exchange** pack (*7 tasks · 3 parts · 3 readings*); fills NAME *Meter exchange — residential* · SERVICE Electric · JOB TYPE Meter exchange · APPLIES TO ASSET TYPES *Electric meter · AMI single-phase · Water meter 5/8"–1"* · SKILL NEEDED Meter fitting · CREW SIZE 1 · SAFETY KIT Standard electrical; the four *What the technician sees* boxes ticked | **Nothing in the database.** Steps 2–6 are prefilled from the pack — every row editable. The footer reads *Step 1 of 8 · nothing is saved to a work order until you Publish. Editing a published template never changes work already in the field.* | The pack is platform data in `apps/work/packs/` — **prefill only, never stored as a link**; `GET /work/template-packs` returns the three platform packs and none of Brazos Bend's templates as a pack. The JOB TYPE help line reads *From the job type catalogue* and **does not** carry the drawn `WM-04` (B14 rule 32). Asset types are rows pointing at `assets` asset types through `assets_seam` — a cross-module FK in the reviewed set, never a copy | **BR-WRK-011** · BR-MET-109 · `US-WRK-016` TC-1 · B14 rule 32 |
| 7 | Steps 2–7: SAFETY 3 rows (*Isolate at the service head before removal · Check for backfeed / on-site generation · Confined space check where pit-set*, all mandatory) · TASKS the seven of `Work-015` (3 + 2 + 10 + 15 + 2 + 5 + 8 = **45 min**; tasks 2 and 5 *photo Required*) · MATERIALS `MTR-E1P` ×1 · `SEAL-01` ×1 · `GSKT-STD` ×1 · READINGS the three of `Work-016` (*Final read on old meter · kWh · 0–99,999 · photo Required · posts on approval* · *Opening read on new meter · kWh · 0–999 · Required · posts* · *New meter serial · — · Optional · recorded only*) · HELP *Meter exchange SOP v4 (PDF)* · *Supervisor · M. Torres · (512) 555-0138* · *AMI activation hotline · ext 44* · SIGNATURE required, refusal recorded with a reason | Alex presses **Save draft** at step 5: ONE `work_order_templates` row with `active = false`, `version` NULL, `template_no` NULL, and its `wot_*` child ROWS — **no JSON blob**. Dragging task 6 above task 5 rewrites `wot_tasks.seq` for the two rows only | ⛔ A reading with prompt *Final read (kWh)* and **no unit** is REFUSED — the unit is a COLUMN, never a word in the prompt (hard rule 3, `BR-WRK-015`). ✅ A task with `est_minutes = 0` and `is_mandatory = true` is ACCEPTED (a mandatory zero-minute check is lawful). ⛔ A draft migration adding a `bundle` jsonb column fails the schema test. The step-3 `ConsequenceBox` reads *45 minutes total is what the dispatcher sees when scheduling*. **Closing the tab at step 7 leaves NO row with `active = true`** — a draft row only because Save draft was pressed | **BR-WRK-009** · **BR-WRK-015** · **BR-WRK-011** · `US-WRK-014` TC-2/TC-3/TC-4/TC-5 · `US-WRK-016` TC-2 |
| 8 | **Step 8 Review** (`Work-017`) | Panel *METER EXCHANGE — RESIDENTIAL · ELECTRIC · 7 SECTIONS · 26 ITEMS*: Details 4 · **Safety 3 — *Blocks the task list until all three are ticked*** · Tasks 7 · Materials 3 · Readings 3 · Help & support 3 · Signature 3; each row with a pencil back to its step. `ConsequenceBox` before the button: publishing affects **new** work orders only (on a first publish there is no previous version; the sentence stands without the drawn *"the 4 orders already raised"* clause, which is `J67`'s state) | **Delete** is a danger-tier button and is ENABLED here — no order references this draft yet; the `NoteBar` reason (*Delete is disabled because this template has produced work orders*) appears only once one does (`J67` step 8). ⛔ Pressing **Publish twice quickly** produces **one version and one `ST-` number** — idempotent on the draft id (`BR-SHL-019`'s single-flight shape) | **BR-WRK-011** · **BR-WRK-012** · `US-WRK-016` TC-3/TC-4 |
| 9 | Alex presses **Publish template** (2 Mar 2026 11:40) | `publish_work_order_template` — **THE ONE WRITE**: `version = 1`, `active = true`, **`template_no = ST-0001` allocated INSIDE the publish transaction** from the tenant's own series (`BR-TEN-035`), one `work_order_template_versions` row (`change_note` *First publish*), one `audit_log` row (actor Alex Reed) | `Work-019` now reads `ST-{0000}` **next 2 · sample `ST-0002`**. `Work-022` for `ST-0001`: kicker *SERVICE TEMPLATE · … · V1* · `StatusPill.green` *Active* · Versions tab **v1 · 02 Mar 2026 · A. Reed · First publish · 0 orders · Current**; Usage tab *0 orders raised*. `Work-013` footer moves to *7 templates · 5 published · 1 draft · 1 inactive*; the new row's Contents reads **7 tasks · 3 parts · 3 readings**, Gate —, Skill Meter fitting, Est. 45 min. ⛔ Changing the series format to `TMPL-{000}` afterwards leaves `ST-0001` exactly as issued — issued numbers are never renumbered | **BR-WRK-011** · **BR-WRK-012** · **BR-WRK-021** · BR-TEN-035 · `US-WRK-012` TC-2/TC-3 · `US-WRK-015` TC-2 |
| 10 | **The seeded starters, as bundles.** Alex opens a starter on `Work-013` | Marked *seeded*; editable; deletable while no order references it; **re-seeded through `templates_svc`, never straight through the model** — a test greps `sample_data.py` for `WorkOrderTemplate.objects.create` and fails on a hit | On an all-eleven-services tenant: **24 rows, 8 with `is_gate`; the gas gate is *Pressure test and light-up* and the gas *Meter set* row's `is_gate` is FALSE** — the row a copying lane gets wrong. Sewer · storm water · solar carry **zero gates and a stored reason each** (*gated on the water service it derives from* · *assessed from records, no visit* · *the gate is permission to operate, which names no step*). Gate `g7x_seeded_starters_have_a_reader.py` PASSES; **removing the Fire starters from the list endpoint's queryset makes it FAIL naming the two rows — proved RED first** (law 7) | **BR-WRK-013** · **BR-WRK-014** · `US-WRK-019` TC-1–TC-6 · `US-WRK-015` TC-4 |
| 11 | **M. Torres** opens the New Connect wizard for **`12 Heron Way`** — steps 1–5 as `J27` (owner, scope *A new premise* · 1 unit, address, unit `1`, services **Electric + Water**) — and reaches **step 6** (`Work-004`) | **Still nothing in the database** (`BR-MET-112`). Step 6 proposes **5** orders, read from `GET /connections/proposed-work-orders?services=electric,water`: Electric *Service drop → Meter set 🚩*; Water *Site inspection & mark-out → Tap and service line → Meter set 🚩*, each carrying its template's `is_gate` and version | **The just-published *Meter exchange — residential* is NOT among the five** — asserted by name (see the disagreement note above). ⛔ A Water template in `draft` is NOT proposed; only published versions are. M. Torres removes *Site inspection & mark-out* → the proposal reads **4**; that is wizard STATE only. ⛔ **Refresh at step 7: no connection, no order, no reserved number exists** — steps 1–8 issue no write; the only reads are `GET /plans?status=published` and the proposal above. ⛔ *We schedule it* stays DISABLED with one sentence — *crew, skill, date, priority and dispatch come with the Work module* — until `EP-WRK-05` lands (`OQ-249`, placement half closed 2026-09-03) | **BR-WRK-016** · BR-MET-112 · BR-MET-109 · `US-WRK-017` TC-1–TC-4/TC-7 |
| 12 | **The commit is NOT this journey's.** M. Torres stops at step 6 | Zero `work_orders` rows for `12 Heron Way`; zero `connections` rows. **`J27` step 10 is the commit and `J61` starts from it** (`CON-26-0129` with four orders) | Nothing money-bearing exists anywhere in this journey: no invoice, no journal line, no payment (`BR-WRK-004`'s shape — Work touches none of hard rule 4's tables). Every reference-data edit and the publish wrote its `audit_log` row (hard rule 7's shape, applied to a non-money module by `BR-WRK-` Part 0) | BR-MET-112 · hard rule 7 |
| 13 | **ISOLATION — Lone Star Ridge WSC** (`app.tenant_id` = Lone Star's; RLS `FORCE` on every Work table) | Its Skills picker lacks *Backflow*; its Type picker holds its own eight; its `Work-013` lists its own starters and **no *Meter exchange — residential***; its packs are the three platform packs and none of Brazos Bend's templates | `GET /lone-star-ridge/work/templates/{brazos-ST-0001-id}/tasks` → **`404`, byte-identical to an absent row**. Lone Star's first publish allocates **its own `ST-0001`**; Brazos Bend's counter (now 2) is untouched. Lone Star adds skill *Chlorination* → absent from Brazos Bend's picker. Every seam read with `app.tenant_id` unset returns zero rows | hard rule 1 · `US-WRK-009` TC-5 · `US-WRK-012` TC-5 · `US-WRK-013` TC-5 · `US-WRK-014` TC-6 · `US-WRK-016` TC-6 · `US-WRK-017` TC-6 |

**This journey leaves (for downstream).** `ST-0001 · Meter exchange — residential · v1 ·
Active`, 3 safety · 7 tasks · 3 materials · 3 readings · 3 help, signature required —
the template `J62`'s worked example (`WO-4822`) and `J63`'s asset door copy from; skill
*Backflow* and type *Backflow test* in the catalogues; `Work-019` reading `ST` next 2;
a template proposal of 5 (4 after one removal) held in wizard state at step 6; **no work
order and no connection** — `J27` step 10 commits and `J61` continues.

## Boundaries — what this journey stops at, and why

| # | Not asserted | Because |
|---|---|---|
| a | A stock level, a reorder point, a location, or *Issues deduct stock* on `Work-025` | **`OQ-WRK-1490`, OPEN.** The register ships without them; step 3 asserts their ABSENCE by key name and the stub that raises. `Work-025` draws them and the card refuses them — `DEF-WRK-3550` |
| b | What a dispatch batch is, or any allocation from `DSP-{YY}{MM}{DD}-{00}` | **`OQ-WRK-1497`, OPEN, non-blocking.** Step 4 asserts no allocator exists |
| c | The commit at step 9 of the New Connect wizard | `J27` step 10 owns it; `J61` continues from it. This journey ends at the proposal, which is phase 1's exit |
| d | The location of the six existing tables (`apps/metering/connections.py` vs `apps/work/`) | PENDING the blueprint's §16 (`03-field-map.md` §4). It moves no rule; the spec addresses tables by name, not by app |
| e | Whether a `Work-` number ever renders on screen | Unruled (`BR-WRK-005`); the staff badge shows r10's module id and `g29` is not pointed at these |
