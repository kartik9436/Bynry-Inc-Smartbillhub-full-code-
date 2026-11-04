# J67 — Template v2 leaves the field work untouched (`ST-0002 · Meter exchange — residential` goes from six tasks to seven; the Versions tab reads *v2 · Current* over *v1 · 4 · Superseded*; the four v1 orders still show six tasks, and so does D. Ortiz's phone)

---
id: J67
tier: 2
rules: [BR-WRK-008, BR-WRK-009, BR-WRK-011, BR-WRK-012, BR-WRK-013, BR-WRK-016, BR-WRK-021, BR-MET-109, BR-SHL-025, BR-TEN-035]
stories: [US-WRK-006, US-WRK-015, US-WRK-016, US-WRK-018, US-WRK-032]
# ⚠ **NOT ACTIVATED** — no `J67.spec.ts`. At HEAD a template is *"one row with ten
# columns"* with no versions, no children and no screen to author one, and an order's
# only template reference is a `template_id` the caller supplies. Written as the HANDOFF
# CONTRACT before the code.
#
# `stories:` = `04-flows.md`'s index for `J67` plus `US-WRK-006` (names all eight).
---

**Intent.** *"Copy, never link"* as **a number on a screen and not a rule in a
document** (`US-WRK-018`). A supervisor publishes v2 of the template four orders were
raised from, one of them in a technician's hand; the journey proves that **nothing in
the field changed** — the four orders still carry six tasks, the phone still shows six,
and only orders raised AFTER the publish carry seven. Around it, the three guards of
`BR-WRK-012`: **Delete is refused while any version is referenced**, **Deactivate stops
new orders and leaves the old ones readable**, and **a superseded version is read-only**.
The consequence box on `Work-017` says it before the button.

**Upstream leaves (the seed — `US-WRK-006`, phase-1 half, at its v1 state).** Tenant
**Brazos Bend Utilities**. **`ST-0002` · Meter exchange — residential · Electric · job type
Meter exchange · skill Meter fitting · crew 1 · safety kit Standard electrical · v1 ·
published 04 Jan 2026 by A. Reed · change note *First publish · 6 tasks*** — 3 safety ·
**6 tasks · 40 min** (the seven of `Work-015` **without** task 6 *Apply tamper seal & log
seal number · 5 min*) · 3 materials · 3 readings · 3 help · signature required.
**Four orders raised from v1**, each stamping `template_version = 1` and holding its own
copy of six tasks: **`WO-4835` · `WO-4836` · `WO-4837` · `WO-4838`** (*this journey's
allocation; `Work-022` gives the count, not the numbers*) — `WO-4838` · `31 Pine Row ·
A-10520` (*ours*) assigned to **D. Ortiz** for **28 Feb 2026 15:00**, its bundle synced
to his phone at 07:50. Actors: **M. Torres** (publishes v2) · **D. Ortiz**. Isolation
tenant **Lone Star Ridge WSC** with its own `ST-0002` (its second published template)
or none.

**The journey's clock.** **Sat 28 Feb 2026**, publish at **14:20** — the date `Work-022`
draws for v2. `J63`'s first sweep (28 Feb → 1 Mar) and `J62`'s fixture `WO-4822`
(raised 15 Mar) copy the v2 this journey leaves.

**Where two documents disagreed, and which one this journey follows.**
* **v1's task count and the template's number** — `04-flows.md`'s `J60` leaves *ST-0001
  with 7 tasks*; `Work-022`, `US-WRK-018` and `04-flows.md`'s `J67` say v1 had **6** and
  the template is **`ST-0002`**. This journey starts from the SEED's v1 (six tasks,
  `ST-0002`), not from `J60`'s output. **Filed as `DEF-WRK-3572`** (also noted at `J60`); corrected 2026-09-03.
* **`Work-022`'s kicker** reads *40 min · 1 technician* while `Work-013` reads *45 min*
  for the same template (`03-field-map.md` D-6). Under this journey's reading both are
  true of a version: **v1 = 6 tasks · 40 min; v2 = 7 tasks · 45 min** — the kicker
  after publish should read 45. Recorded; the spec asserts the per-version figure.
* **The change note** `Work-022` draws — *Added Apply tamper seal; opening-read max 999 →
  999* — has a clause that changes nothing (D-6). The note is user-input at publish; the
  fixture keeps the drawn string and the spec asserts the **task delta**, not the note.
* **The drawn ORDERS RAISED for v2 is 31** — a month of raises after the publish. At the
  moment of publish it is **0**; step 6 asserts 0 and that later raises stamp v2.

| # | Actor · action · screen | Expected outcome (contract — what this step leaves) | Downstream assertions (record · phone · screen · audit) | Rule |
|---|---|---|---|---|
| 1 | **28 Feb 13:50 · M. Torres** opens `Work-022` for `ST-0002` → **Versions** tab | Kicker *SERVICE TEMPLATE · METER WORK · V1* · title *Meter exchange — residential* · meta *40 min · 1 technician ·* `StatusPill.green` *Active* · `ActionRow` **Edit template · Duplicate · Deactivate · Delete (danger, DISABLED)**. VERSIONS: **`v1 · 04 Jan 2026 · A. Reed · First publish · 6 tasks · 4 · Current`**; `CountFooter` *4 orders raised across 1 version*; `NoteBar` **Delete is disabled while any order references any version. Deactivate stops new orders and leaves the 4 readable.** | Usage tab: *4 orders raised*, per-version breakdown v1 = 4, **summing to the total**. `Work-013` lists the template *Published · 6 tasks · 3 parts · 3 readings · 40 min*. ⛔ `DELETE /work/templates/{ST-0002}` → **REFUSED naming the count** (4) — the button is disabled with that reason AND the server refuses (`BR-SHL-025`) | **BR-WRK-012** · BR-SHL-025 · `US-WRK-018` TC-4/TC-7 · `US-WRK-015` TC-3 |
| 2 | **D. Ortiz's phone**, before anything changes | `WO-4838 · Meter exchange · 31 Pine Row · 15:00 · 40 min`; the job shows **TASKS — 6 STEPS · 40 MIN** — its own copy, `template_version = 1` | The order's task table has **no FK to `wot_tasks`**; the only template reference on the order is `template_id` + `template_version` (schema test) | **BR-WRK-008** · `US-WRK-032` TC-6 |
| 3 | M. Torres presses **Edit template** → the builder opens on the current version **as a draft of v2**; on **step 3** (`Work-015`) adds a task with the inline add row — *Add a task…* **Apply tamper seal & log seal number** · *Minutes* **5** · Photo — · **+ Add** — and drags it to **position 6** (after *Record opening read on new meter*, before *Restore supply & confirm flow*) | The draft's `wot_tasks.seq` rewritten for the moved rows; header **TASKS — 7 STEPS · 45 MIN TOTAL**; `ConsequenceBox` *45 minutes total is what the dispatcher sees when scheduling. Estimates that are wrong here make every day's route wrong.* M. Torres presses **Save draft** | **A draft is not a version**: `Work-013` still lists v1 *Published*; `Work-022`'s Versions tab still reads one version; **the four orders are untouched**; D. Ortiz's phone (re-synced) still reads **6 STEPS · 40 MIN**. ⛔ Closing the tab at step 5 leaves the draft and **no** second `active` version | **BR-WRK-011** · **BR-WRK-009** · **BR-WRK-008** · `US-WRK-016` TC-2 · `US-WRK-014` TC-2 |
| 4 | **Step 8 Review** (`Work-017`) | Panel *METER EXCHANGE — RESIDENTIAL · ELECTRIC · 7 SECTIONS · 26 ITEMS* — Details 4 · Safety 3 · **Tasks 7 · Seven tick boxes · 45 min · 2 require a photo** · Materials 3 · Readings 3 · Help & support 3 · Signature 3. `ConsequenceBox`, **before the button**: ***Publishing affects new work orders only. The 4 orders already raised from the previous version keep exactly what they were given — nothing in the field changes.*** `ButtonRow` **← Back · Publish template · Save as draft · Delete (danger, disabled)**; `NoteBar` *Delete is disabled because this template has produced work orders. Deactivate it instead — the orders keep their meaning and no new ones are raised from it.* | The **4** in the box is computed from `work_orders` by (template_id, template_version), not typed. ⛔ **Publish pressed twice quickly → ONE version (v2), no v3** — idempotent on the draft id | **BR-WRK-011** · **BR-WRK-012** · B14 rule 11 · `US-WRK-016` TC-3/TC-4 |
| 5 | **14:20 · Publish template** | `publish_work_order_template`: **`version = 2`**, `active = true`, one `work_order_template_versions` row (`version 2 · published_at 28 Feb 14:20 · published_by M. Torres · change_note` *Added Apply tamper seal; opening-read max 999 → 999*), **`template_no` unchanged — `ST-0002`** (the number was allocated at the FIRST publish; a version allocates nothing — `Work-019`'s `ST` counter does not move), one `audit_log` row | `Work-022` Versions: **`v2 · 28 Feb 2026 · M. Torres · Added Apply tamper seal; … · 0 · Current`** over **`v1 · 04 Jan 2026 · A. Reed · First publish · 6 tasks · 4 · Superseded`**; `CountFooter` **4 orders raised across 2 versions · The 4 v1 orders still read v1 — nothing was rewritten**; kicker *V2*; meta **45 min · 1 technician** (the per-version figure; the drawn 40 is v1's — D-6). `Work-013`: *7 tasks · 3 parts · 3 readings · 45 min · Published* | **BR-WRK-012** · **BR-WRK-021** · BR-TEN-035 · `US-WRK-018` TC-1 · `US-WRK-012` TC-2 |
| 6 | **The four v1 orders, and the phone.** M. Torres opens `WO-4838` on `Work-008` → Checklist; D. Ortiz re-syncs at 14:25 | `Work-008`: **TASKS — 6 STEPS · 40 MIN ESTIMATED**, no *Apply tamper seal*, `template_version = 1`; the same for `WO-4835`–`WO-4837`. **D. Ortiz's phone still shows 6 STEPS · 40 MIN** — the bundle is the order's copy, versioned by the order's `updated_at`, which did not move | ✅ **`WO-4835`–`WO-4838`'s `work_order_tasks` rows are byte-identical to before the publish** (a checksum per order, before and after). ✅ D. Ortiz works `WO-4838` at 15:00 against six tasks and closes it — the report will read *6 of 6*. The **first order raised after 14:20** — `J63`'s `WO-4918` on 1 Mar, `J62`'s `WO-4822` on 15 Mar — copies **seven** tasks and stamps **`template_version = 2`**; the Versions tab's ORDERS RAISED for v2 moves from 0 with each | **BR-WRK-008** · **BR-WRK-012** · `US-WRK-018` TC-2 · `US-WRK-032` TC-1/TC-3 · `US-WRK-042` TC-3 |
| 7 | **Negative — edit the superseded version.** M. Torres opens v1 from the Versions tab and tries to rename its task 3 | **REFUSED — a superseded version is read-only**; the sentence ≤ 6 words. The only editable thing is a NEW draft (of v3) from the current version | Renaming task 3 on the DRAFT of v3 and reloading `WO-4838` still reads *Isolate supply & remove old meter* — the order's copy never changes (`US-WRK-032` TC-2) | **BR-WRK-012** · **BR-WRK-008** · `US-WRK-018` TC-3 · `US-WRK-032` TC-2 |
| 8 | **Negative — Delete, with orders referencing two versions** | `Work-022`'s **Delete** disabled with its reason; **`DELETE /work/templates/{ST-0002}` → REFUSED naming the count** — *"Delete is refused while any version is referenced"* | Duplicate → a NEW draft carrying every child row, `version` unset, name suffixed *(copy)*, **no `template_no` until it is published** | **BR-WRK-012** · BR-SHL-025 · `US-WRK-018` TC-4 · `US-WRK-015` TC-7 |
| 9 | **Deactivate — asserted on the fixture's *Backflow test* (Inactive), so `ST-0002` stays active for `J63` and `J62`.** M. Torres opens `Work-013`'s *Backflow test · Water · Inactive* | `active = false`: **New Connect step 6 does not propose it**; the `Work-028` template picker and the New order wizard do not offer it; a rule at *Review & activate* naming it is refused; **`POST /work-orders` from it is REFUSED** (the shape `US-WRK-034` TC-3 relies on); **its existing orders open unchanged and readable** — Deactivate *stops new orders and leaves the old ones readable* | On `ST-0002`, the **Deactivate** control is OFFERED with the `NoteBar` sentence; pressing it would do exactly the above to the template `J63`'s sweep and `J62`'s fixture depend on, so it is **not pressed here**. ⚠ `07-endpoints.md` §3 has `deactivate` (#44) and **no reactivate route**; whether `PATCH /work/templates/{id}` (#40) may set `active` back to true was not stated — **settled 2026-09-03 (`DEF-WRK-3579`, decision log): #44a `POST /work/templates/{id}/reactivate` is the way back, and `PATCH` never touches `active`** | **BR-WRK-012** · **BR-WRK-016** · `US-WRK-018` TC-5 · `US-WRK-017` TC-4 |
| 10 | **The seeded starters and the gas gate, unchanged by any of this** (`Work-013`) | The 24 starters still marked *seeded*; the **Gas *New connection* gate is still *Light-up 🚩***; sewer · storm water · solar still carry no gate and their stored reasons | A version publish on ONE template touches no other row: `work_order_templates` count unchanged but for the draft; the gate `g7x_seeded_starters_have_a_reader.py` still passes | **BR-WRK-013** · BR-MET-109 |
| 11 | **ISOLATION — Lone Star Ridge WSC** (`app.tenant_id` = Lone Star's) | `/lone-star-ridge/work/templates/ST-0002` → **its own `ST-0002` or `404` — never Brazos Bend's**; its Versions tab shows its own history; `PUT /lone-star-ridge/work/templates/{brazos-id}/tasks` → `404`; Lone Star's v2 publish on any of its templates moves **its** counters only | Brazos Bend's four v1 orders and one v2 draft are invisible under Lone Star's `app.tenant_id` | hard rule 1 · `US-WRK-018` TC-6 · `US-WRK-015` TC-6 |
| 12 | **INVARIANCE** | — | **Two versions, one number.** Every order stamps the version it was raised from and **no order's copy changed** through the publish (four checksums equal); a v1 order's task table has **no FK** to the template's; the per-version counts always sum to Usage. Publish was the one write; the draft before it reached no order. Nothing money: no cost, no posting. Every publish and every refused delete audited | **BR-WRK-008** · **BR-WRK-011** · **BR-WRK-012** · hard rule 7 · BR-TEN-035 |

**This journey leaves (for downstream).** `ST-0002` at **v2 · Active · 7 tasks · 45 min**
(v1 Superseded, read-only) · four v1 orders each still holding **six** tasks, `WO-4838`
closed against them · D. Ortiz's phone showing six on that job · **0** orders on v2 at
publish, the count moving with every later raise · Delete refused, Deactivate offered and
not pressed · Lone Star Ridge untouched. **Downstream:** `J63`'s sweep (1 Mar) and
`J62`'s `WO-4822` (15 Mar) copy this v2 — seven tasks, `template_version = 2`.

## Boundaries — what this journey stops at, and why

| # | Not asserted | Because |
|---|---|---|
| a | Deactivating `ST-0002` itself | Downstream journeys copy it; the effects of deactivation are asserted on the fixture's inactive *Backflow test* (step 9). Whether a deactivated template can be reactivated was not stated in `07-endpoints.md` until 2026-09-03: #44a `reactivate` now is, and `PATCH` never touches `active` (`DEF-WRK-3579`) |
| b | The drawn *31* orders on v2 | A month of raises after the publish; at 14:20 it is 0 and the spec asserts the count moves with `J63`/`J62`'s raises |
| c | `WO-4835`–`WO-4838` and `31 Pine Row · A-10520` | This journey's fixture values (*ours*); `Work-022` gives the count only. Should be written once in `US-WRK-006` |
| d | The `J60` ↔ `J67` collision on `ST-0001`/`ST-0002` and 7-vs-6 tasks at v1 | Filed as `DEF-WRK-3572` and closed 2026-09-03 — two fixture states of one tenant, stated in `US-WRK-006` §4; this journey follows `Work-022`, `US-WRK-018` and `04-flows.md`'s own `J67` text |
| e | The change note's *999 → 999* clause | D-6 in `03-field-map.md`; the note is free text at publish and the spec asserts the task delta |
