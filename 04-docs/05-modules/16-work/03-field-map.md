# 16 · Work — field map

**Every table below is tenant-scoped and every one carries RLS `FORCE` in the same
migration that creates it** (CLAUDE.md hard rule 1; `CR-070` §3: *"RLS policy in the same
migration"*). **Money is `NUMERIC(18,4)`, percentages `NUMERIC(18,6)`, both display 2**
(hard rule 2). A quantity carries its unit (hard rule 3).

⚠ **THE BUILD SPECIFICATION IS UNREAD.** The blueprint's §16 — *"23 new tables, columns,
endpoints"* by its own headline — sits past the text this lane could read. **Everything in
this file is assembled from the commitment cards (§4–§14), the wireframes' *Rests on*
lines and the six tables that already exist in the code.** Where a table or column is the
card's it is marked `[card]`; where it is ours because a card or wireframe needs it and
names no column, it is marked `[ours — §16 unread]`. **When §16 is read, §16 wins on every
row here, and this file is stamped, not silently overwritten.** The cards name **25**
tables; §16 says **23**; the gap is recorded in §5 and not resolved here.

---

## 1 · The six tables that already exist — `apps/metering/connections.py`, migrations `metering 0026`/`0027`

*"Six tables, created by migrations `metering/0026` and `0027`, every one tenant-scoped
with row-level security set to FORCE. The classes live in `connections.py` rather than
`models.py` — deliberately, so two lanes editing one models module could not fork the
migration graph."* Verified at HEAD `654034ed` by the predecessor lane (2026-09-03).

| Table | Columns today (as the model declares them) | What changes |
|---|---|---|
| `connections` | `connection_no` (`CON-{YY}-{0000}`) · `state` (a cache, written only by `refresh_connection_state()`) · `mode` (default) · `waiting_on` · `target_activation` · `quote_total` · `owner_account_id` · `submitted_at` · `held_at` · `cancelled_at` | nothing |
| `connection_services` | `unit_id` · `service_id` · `state` (one of five) · unique per unit + service | nothing |
| **`work_orders`** | `order_no` (`WO-{0000}`) · `connection_id` **NOT NULL** (`connections.py:699–701`) · `type` (free text) · `scope` · `service_id` · `unit_id` · `asset_id` (a real, migrated, RLS-scoped FK **written by nothing**) · `blocked_by` (self) · `state` (`planned · in_progress · blocked · completed · cancelled`) · `outcome` (`passed · failed · partially_done · cancelled · waiting_on_someone_else`) · `mode` (`our_crew · external · we_schedule ⛔`) · `template_id` · `is_gate` (stamped) · `external_ref` · `completed_at` · `attachment_ref` (**dead — written and read by nothing**) · `field_data` (jsonb) · `accepted_by` · `accepted_at` · `is_sample` · indexes `(tenant, connection)`, `(tenant, state)` | **§3 below — the largest change set** |
| **`work_order_templates`** | `service_id` · `sequence` · `name` · `scope` · `skill` (free text, **NULL on all 24 seeded rows**) · `est_duration` (interval) · `is_gate` · `is_sample` · **`unique(service, sequence)`** | **§3 below** |
| `connection_todos` | `title` · `detail` · `source` (`human · suggested`) · `marked_by` · `closed_by` · never blocks the build | nothing |
| `service_characteristics` | `unit_id` · `service_id` · `key` · `value` · `unit_of_measure` · unique per unit + service + key (`BR-MET-108`) | nothing |

---

## 2 · The new tables — 25 named in cards, plus what the wireframes and stories need

### 2.1 · Reference data — `EP-WRK-02` (phase 1)

| Table | Card | Columns | Owner story |
|---|---|---|---|
| `work_order_types` `[card]` | `WM-04` | code · name · default_priority_id · default_template_id NULL · est_duration · customer_present · active · unique (tenant, code) | `US-WRK-007` |
| `work_priorities` `[card]` | `WM-05` | code · name · rank · sla_hours · colour · unique (tenant, code), (tenant, rank) | `US-WRK-008` |
| `work_skills` `[card]` | `WM-06` | code · name · active | `US-WRK-009` |
| `work_safety_kits` `[card]` | `WM-06` | code · name · items text[] | `US-WRK-009` |
| `part_categories` `[card]` | `WM-06` | code · name | `US-WRK-009` |
| `parts` `[card]` | `WM-07` | part_no · name · category_id · unit_of_measure · unit_cost `numeric(18,4)` · active · unique (tenant, part_no). **No `on_hand`, no `reorder_at`, no `location`** — `OQ-WRK-1490` | `US-WRK-010` |
| `labour_rates` `[card]` | `WM-45` | role · hourly `numeric(18,4)` · overtime_hourly NULL · overtime_after_hours NULL · effective_from · superseded_on NULL — **append-only; one current per role** | `US-WRK-051` |

### 2.2 · The template bundle — `EP-WRK-03` (phase 1)

| Table | Card | Columns | Owner story |
|---|---|---|---|
| `wot_details` `[card]` | `WM-09` | template_id · show_account_summary · show_asset_card · show_access_notes · show_appointment (one row per template) | `US-WRK-014` |
| `wot_safety` `[card]` | `WM-09` | template_id · seq · text · is_mandatory | `US-WRK-014` |
| `wot_tasks` `[card]` | `WM-09` | template_id · seq · title · est_minutes · photo_required · is_mandatory | `US-WRK-014` |
| `wot_materials` `[card]` | `WM-09` | template_id · part_id · planned_qty · unit_of_measure | `US-WRK-014` |
| `wot_readings` `[card]` | `WM-09`, `WM-29` | template_id · seq · prompt · **unit_of_measure** · min · max · required · photo_required · **posts_as_meter_read** | `US-WRK-014`, `US-WRK-046` |
| `wot_help` `[card]` | `WM-09` | template_id · seq · kind ∈ {document, phone, note} · label · ref | `US-WRK-014` |
| `wot_asset_types` `[card]` | `WM-09` | template_id · asset_type_id (→ `assets`, via the seam; a cross-module FK in the reviewed set) | `US-WRK-014` |
| `work_order_template_versions` `[ours — §16 unread]` | `WM-40` says *"lists versions with what changed"* | template_id · version · published_at · published_by · change_note · orders_raised (computed) | `US-WRK-018` |

### 2.3 · Workforce — `EP-WRK-04` (phase 2)

| Table | Card | Columns | Owner story |
|---|---|---|---|
| `crews` `[card]` | `WM-13` | name · kind ∈ {crew, contractor} · headcount · shift_start · shift_end · active | `US-WRK-020` |
| `technicians` `[card]` | `WM-13` | user_id (→ `identity.users`, reviewed set; unique per tenant) · role_label · shift_start · shift_end · van · status ∈ {on_shift, off_today, unavailable} | `US-WRK-020` |
| `technician_skills` `[card]` | `WM-13` | technician_id · skill_id · proficiency ∈ {trained, certified} | `US-WRK-020` |
| `technician_certifications` `[card]` | `WM-21` (*"certifications-per-person"*) | technician_id · certification_type_id (→ `tenancy.certification_types`, reviewed set) · expires_on · evidence_document_id NULL | `US-WRK-021` |
| `technician_devices` `[ours — §16 unread]` | `WM-37` needs a push target | technician_id · token · platform · registered_at · active | `US-WRK-030` |

### 2.4 · Dispatch and the order — `EP-WRK-05`, `EP-WRK-06` (phase 2)

| Table | Card | Columns | Owner story |
|---|---|---|---|
| `work_order_assignments` `[card]` | `WM-15` | work_order_id · act ∈ {assign, unassign, schedule, depart, arrive} · technician_id NULL · crew_id NULL · scheduled_for NULL · window_start/end NULL · actor_id · at — **append-only trigger** | `US-WRK-025` |
| `work_order_tasks` `[card]` | `WM-18` | work_order_id · seq · title · est_minutes · photo_required · is_mandatory · ticked_at · ticked_by · photo_attachment_id NULL — **a copy; no FK to `wot_tasks`** | `US-WRK-032` |
| `work_order_readings` `[card]` | `WM-18`, `WM-35`, `WM-49` | work_order_id · seq · prompt · unit_of_measure · min · max · required · **photo_required** (the rule) · posts_as_meter_read · value NULL · captured_at · captured_by · **photo_attachment_id NULL** (the file) · in_range NULL (server-derived) | `US-WRK-032`, `US-WRK-047`, `US-WRK-049` |
| `work_order_materials` `[card]` | `WM-18`, `WM-22` | work_order_id · part_id · planned_qty · used_qty · unit_of_measure · issued_by · issued_at · unplanned | `US-WRK-032`, `US-WRK-050` |
| `work_order_safety` `[ours — the `WS-08` caption says "six order instance tables"]` | `WM-18` (three named) | work_order_id · seq · text · is_mandatory · ticked_at · ticked_by | `US-WRK-032`, `US-WRK-043` |
| `work_order_help` `[ours — same]` | `WM-18` | work_order_id · seq · kind · label · ref | `US-WRK-032`, `US-WRK-042` |
| `work_order_details` `[ours — same]` | `WM-18`, `WS-10` | work_order_id · access_notes · hazards · gate_code · show flags | `US-WRK-032`, `US-WRK-041` |
| `work_order_attachments` `[card]` | `WM-30`, `WM-48` | work_order_id · document_id (→ `stored_documents`) · kind · taken_at · device · added_by · reading_id NULL · task_id NULL · idempotency_key unique | `US-WRK-036`, `US-WRK-048` |
| `work_order_signatures` `[card]` | `WM-30` | work_order_id (one row) · printed_name · document_id · signed_at · captured_by · refused · decline_reason · door_hanger_document_id | `US-WRK-036` |
| `work_order_rules` `[card]` | `WM-24` | name · source_module ∈ {payments, billing, assets, reads, accounts} · trigger_kind · trigger_params jsonb · template_id · priority_id · assignment · assignee · notifications jsonb · escalation jsonb · enabled | `US-WRK-037` |
| `work_sync_receipts` `[ours — §16 unread; `WM-36` unread]` | `WM-48`'s per-item key | tenant · key unique · order_id · kind · accepted_at | `US-WRK-044` |
| `part_issues` `[ours — `WM-22` says "issues and returns"]` | `WM-22`, `WS-25` | part_id · qty (signed) · issued_to_technician_id NULL · issued_to_crew_id NULL · purpose · order_ref **text, by design** · recorded_by · at | `US-WRK-050` |
| `work_order_reports` `[ours — `WM-47` says "versioned"]` | `WM-47` | work_order_id · version · document_id · generated_at · generated_by · unique (order, version) | `US-WRK-053` |
| `work_order_cost_lines` `[ours — `WM-47`'s cost table needs persisting]` | `WM-47`, `WM-41` | work_order_id · kind ∈ {labour, overtime, part} · description · qty · unit · rate `numeric(18,4)` · amount `numeric(18,4)` | `US-WRK-053`, `US-WRK-054` |

**Count.** Cards name **25**: the seven reference tables of §2.1 (`labour_rates` counted; `WM-45`), the seven `wot_*`, `crews` · `technicians` · `technician_skills` · `technician_certifications`, `work_order_assignments`, the three `WM-18` copies, `work_order_attachments` · `work_order_signatures`, `work_order_rules`. **Ours, because a card or wireframe needs them and names no table: 10** (`work_order_template_versions`, `technician_devices`, `work_order_safety`, `work_order_help`, `work_order_details`, `work_sync_receipts`, `part_issues`, `work_order_reports`, `work_order_cost_lines`, and — not a table — the `DOCUMENT_KINDS` widening). **§16 says 23.** The two-table gap between the cards and §16, and the ten this file adds, are exactly what reading §16 settles; **a lane opening phase 1 reads §16 before `work/0001`.**

---

## 3 · The changed columns — 28 across four existing tables, two of them NOT BUILT

| # | Table (module) | Column | Card | Why | Story |
|---|---|---|---|---|---|
| 1 | `work_orders` (metering → work) | `connection_id` **becomes NULL-able** — **BUILT, `metering/0044` (2026-09-03)** | `WM-01` | *"The structural blocker"* | `US-WRK-001` |
| 2 | `work_orders` | `premises_id` FK NULL — **BUILT, `metering/0044`** | `WM-01` | an anchor beside the connection | `US-WRK-001` |
| 3 | `work_orders` | `account_id` FK NULL — **BUILT, `metering/0044`; B2 Addendum r23 records the FK** | `WM-01` | an anchor; reviewed-set FK | `US-WRK-001` |
| 4 | `work_orders` | `ck_work_orders_has_anchor` CHECK `[ours]` — **BUILT, `metering/0044`; proved on PostgreSQL 16 by a raw INSERT** | — | at least one of connection · premises · account · asset | `US-WRK-001` |
| 5 | `work_orders` | `type_id` FK NULL → `work_order_types` | `WM-04` | beside the free-text `type` until §16 says when it goes | `US-WRK-007` |
| 6 | `work_orders` | `priority_id` FK | `WM-14` | | `US-WRK-024` |
| 7 | `work_orders` | `due_at` | `WM-14` | raise + SLA by default | `US-WRK-024` |
| 8 | `work_orders` | `window_start`, `window_end` (counted as one) | `WM-14` | appointment window | `US-WRK-024` |
| 9 | `work_orders` | `dispatch_state` enum | `WM-14` | the third axis | `US-WRK-024` |
| 10 | `work_orders` | `source` enum | `WM-14` | why it was raised | `US-WRK-024` |
| 11 | `work_orders` | `rule_id` FK NULL | `WM-14` | | `US-WRK-024` |
| 12 | `work_orders` | `assignee_technician_id`, `assignee_crew_id` (one) | `WM-14` | a cache of the latest assignment | `US-WRK-024` |
| 13 | `work_orders` | `assigned_at`, `assigned_by` (one) | `WM-14` | a cache | `US-WRK-024` |
| 14 | `work_orders` | `est_duration` | `WM-14` | copied from the template | `US-WRK-024` |
| 15 | `work_orders` | `area_id` FK → `tenancy.areas` | `WM-28` | | `US-WRK-011` |
| 16 | `work_orders` | `template_version` | `WM-40` | | `US-WRK-018` |
| 17 | `work_orders` | `technician_notes` | `WS-21` `[ours]` | | `US-WRK-031` |
| 18 | `work_orders` | `follows_order_id` FK NULL `[ours]` | `WM-25` | the follow-up names what failed | `US-WRK-034` |
| 19 | `work_orders` | `labour_rate_snapshot` `numeric(18,4)`, `labour_role` (one) | `WM-45` | a closed job keeps its rate | `US-WRK-051` |
| 20 | `work_orders` | `attachment_ref` **DROPPED** | `WM-30` | dead; NULL everywhere | `US-WRK-036` |
| 21 | `work_order_templates` | `type_id` FK | `WM-08` | | `US-WRK-013` |
| 22 | `work_order_templates` | `skill_id` FK NULL **replacing** text `skill` | `WM-08` | | `US-WRK-013` |
| 23 | `work_order_templates` | `crew_size` | `WM-08` | | `US-WRK-013` |
| 24 | `work_order_templates` | `safety_kit_id` FK NULL | `WM-08` | | `US-WRK-013` |
| 25 | `work_order_templates` | `active`, `version` (one) | `WM-08` | | `US-WRK-013` |
| 26 | `work_order_templates` | `template_no` (`ST-{0000}`) | `WM-42` | | `US-WRK-012` |
| 27 | `work_order_templates` | **drop** `uq(service, sequence)`; **add** `uq(tenant, name, version)` | `WM-08` | *"one relaxed key"* | `US-WRK-013` |
| 28 | `stored_documents` (tenancy) | `kind` CHECK gains `work_order_photo`, `work_order_signature`, `work_order_report` — 33 → 36 (one change, three values) | `WM-48` | tenancy owns the table and the migration | `US-WRK-048` |
| — | `taxes` (rating) 🔒 | ~~`base_includes_field_work`~~ · ~~`flat_frequency += per_work_order`~~ | `WM-46` | **NOT BUILT — PO 2026-09-03: *"Dont add Tax on work order - for now"*.** B4 §Tax ❄️ stands | `US-WRK-052` |
| — | `work_order_templates` | `no_gate_reason` text NULL `[ours]` | §11 | *"stored as data with its reason"* | `US-WRK-019` |
| — | `disconnect_cases` (customers) | `field_visit` enum `[ours]` | `WM-44` | **Customers owns the write** — its own wizard's record | `US-WRK-039` |
| — | `users` (identity) | `surface_scope` enum `[ours]` | `WM-31` | identity owns the write; the refusal is stubbed on `OQ-WRK-1494` | `US-WRK-023` |

**28 counted, matching the estimate (~27).** The last three rows are columns on OTHER
modules' tables that those modules write — recorded here so the interface set is
reviewed (B2 §2), not so Work writes them.

---

## 4 · Where the six existing tables live — **DECIDED 2026-09-05: (b)**

`CR-070` §10 puts *"the 23 tables — orders, templates + 7 children…"* in
`apps/work/models.py`, and the ruling makes `work` their owner. **But the six tables exist
in `apps/metering/connections.py` today, with two migrations, an audit trail and tests.**
Three ways to honour the ruling: **(a)** move the six models and their history into
`apps/work/` with Django's `db_table` unchanged (a migration-graph operation, `DEF-892`'s
territory) · **(b)** leave them in metering and have Work read and write them through
metering's seams — which makes `work_orders` a table Work does not own, against the ruling
· **(c)** move `work_orders` and `work_order_templates` (the two Work changes touch) and
leave the four connection tables in metering. ~~**This file records the choice as PENDING
and does not make it**: phase 0's one column (`US-WRK-001`) is a metering migration either
way, and the choice belongs to the lane that writes `work/0001` **after reading §16**.~~ It
moves no rule and is not a PO question.

### ⚠ DECIDED 2026-09-05 — **(b)**, and §16 was never readable

**The choice is (b): the six existing tables STAY in `apps/metering/connections.py`, and every
Work read and write of them goes through `apps/work/seams/metering_seam.py`, which calls
metering's own service by name.** Recorded in `12-governance/02-decision-log.md`, 2026-09-05.

**Why it was decided rather than left pending.** The instruction was *"a phase-1 lane reads
§16 before `work/0001`"*. **§16 cannot be read and never could:** the blueprint is a 16.3 MB
PDF that was over the download cap when this module was written, the text reader stopped
inside §14, and **the file is not in this repository at all** (`find . -iname "*blueprint*"`
returns one directory of customer-portal screenshots). A precondition that can never be met is
not a precondition; it is a block with no expiry, and law 13 says a judgment recorded with its
reasoning is the deliverable.

**And the decision was already taken in code, twice, before this row admitted it.** Wave C
wrote `work/0001` on 2026-09-04 and left the six where they were —
`apps/work/models.py`'s own closing line says so — and added its two template columns through
`metering/0045`. Wave D did the same through `metering/0048`. **A pending decision that two
waves have already acted on is not pending; it is undocumented.**

**What (b) costs, stated rather than glossed.** `CR-070` §10 makes `work` the OWNER of
`work_orders` and `work_order_templates`, and under (b) it owns tables it does not declare.
That is a real gap between the ruling and the schema, and it is why the seam exists in the
shape it does: **every read and the one write already go through one file**, so the day the
models move, `metering_seam.py` changes and nothing that calls it does. `G78` keeps it honest
from the other side — no file under `apps/work/` may import `apps.metering.connections`
outside `seams/`, and none does.

**What (a) would have cost today.** A migration-graph move of six tables with two migrations,
an audit trail, thirty-odd test call sites and a live `metering/0044`..`0048` chain — done on
the side of a wave whose deliverable is a template bundle, with no §16 to check it against.
**The table count settles the same way**: §16 says 23, the cards name 25 and this file adds 10
of its own; nobody can reconcile three numbers against a section nobody can open, so the count
that governs is the one in §2 above, which is measured from the cards and the wireframes.

**When this is revisited.** When the blueprint's §16 becomes readable, or when a wave needs
Work to write `work_orders` directly rather than through `create_work_order`. Neither has
happened; both are visible the moment they do, because the seam is the only door.

### ⚠ REVISITED 2026-10-21 — the DECLARATIONS moved to Work (`CR-187-BRC10` T-43); the services did not

The field-app plan's T-43 took option **(a)** for the model layer: the six classes and the
vocabulary their check constraints read now live in **`apps/work/connection_models.py`**
(registered by `apps/work/models.py`), and the migration state moved with them —
`work/0046_t43_take_the_six_work_tables` creates the six in Work's state and
`metering/0078_t43_release_the_six_work_tables` deletes them from metering's, both
`SeparateDatabaseAndState` with **no database operation**. Every table kept its name, rows,
constraints, indexes and RLS policies; proved on PostgreSQL 16 by an identical before/after
snapshot of `pg_class`, `pg_policies`, `pg_constraint`, `pg_indexes`, the columns and an md5
of every row. Every importer now reads them from `apps.work.connection_models`; the one thin
re-export left in `connections.py` is `DISPATCH_STATES`, because the applied migration
`metering/0050` imports it from there.

**What did not move:** the New Connect and work-order SERVICES (`create_work_order`,
`commit_new_connect`, `accept_field_result`, …) are still in `apps/metering/connections.py`,
so metering code now writes tables Work owns — the mirror of (b)'s gap — and
`metering.ConnectionFeeBill.connection` is now a metering → work FK. Moving the services is
its own piece of work with its own blast radius.

---

## 5 · Discrepancies between the cards, the wireframes and the record

| # | Where | What disagrees | What this module does |
|---|---|---|---|
| D-1 | `WM-07` vs `WS-25` | `MTR-W58` unit cost `$92.4000` (card) vs `78.40` (wireframe) | The card's figure |
| D-2 | `WM-07`/`WM-22` vs `WS-25` | *"No stock levels, no reorder points"* vs On hand · Reorder at · *"Issues deduct stock"* | The card; the columns are not built; `OQ-WRK-1490`; `DEF-WRK-3550` |
| D-3 | `WM-21` vs `WS-23` | *"refusing a job on a lapsed one is out of scope"* vs *"blocked from 4 template types"* | The card; the block is stubbed; `OQ-WRK-1493`; `DEF-WRK-3551` |
| D-4 | `WM-18` vs `WS-08` caption | three order-instance tables vs *"the six order instance tables"* | Six are copied; §16 to settle |
| D-5 | `WS-32` vs PO 2026-09-03 | two tax lines and a total of `149.84` | No tax line; total `138.42`; `US-WRK-052` |
| D-6 | `WS-22` | *"opening-read max 999 → 999"* changes nothing; kicker *40 min · 1 technician* vs `WS-13`'s *45 min* for the same template | Recorded; the fixture uses 45 min |
| D-7 | `WM-13` vs `WS-23` | D. Ortiz *Meter-fitting* (card) vs *Water II · Meter I* (wireframe) | The fixture carries both |
| D-8 | `WS-29` vs §9/§12 | `WO-4907` is the gas light-up on `CON-26-0117` **and** the move-out visit on `A-10688` | The fixture gives the visit `WO-4910` |
| D-9 | `WS-33` vs `WS-16` | a fourth reading, *Voltage at socket*, not on the template's three | Recorded; the fixture adds it to the v2 template so the *required, missing* case exists |
| D-10 | blueprint headline / `CR-070` §0b | *"thirty-eight specifications"* vs 49 cards | 49; `DEF-WRK-3542` |
| D-11 | blueprint §7 / `CR-070` §1 | *"fifteen finished write actions"* vs 16 names, 14 writers | The 14 writers, pinned in `US-WRK-002` |
| D-12 | `WM-44` | *"refuses this act four times"* vs one constant, one payload site, two docstring mentions | Recorded; the design it names is the same |
| D-13 | `WM-29` | the set-read shape `[{meter_no, value, read_at, channel}]` carries **no unit** | The seam call carries `unit`; if metering's door does not take one, that is metering's story, filed not worked around (`US-WRK-046`) |
| D-14 | `WM-47`'s figure | `0.87 h × 48.50 = 42.20` — hours at 2 dp; at 4 dp it is `42.03` | Hours booked to 2 dp, as the card's figure demands; decision-log draft |
| D-15 | §16 vs the cards | **23** tables vs **25** named | Unresolved until §16 is read |
| D-16 | r10 `WS-07`/`WS-10` vs blueprint §9/§12 | **Two fixture generations share one number range.** r10 draws the dispatcher and the phone with `WO-48xx` orders (`WO-4821`–`4830`, `WO-4822` the meter exchange); the blueprint's build narrative puts `WO-4901`–`4907` on `CON-26-0117`. **`WO-4902` is claimed three ways** — `J27`/`US-WRK-006` (`CON-26-0117`, `500 Main St`), `US-WRK-035` (`CON-26-0110`, `3450 Oak Ridge Dr`), `US-WRK-041`'s day list (`3450 Oak Ridge Dr`, 09:15) — and **`WO-4907` is two orders** (D-8) | **Not reconciled, deliberately (2026-09-03, `DEF-WRK-3575`).** The series allocates at raise (`BR-TEN-035`), so no drawn number is a fact about the product: **a spec asserts an order by its KEY — connection or anchor, template, service, position in the build — and never by a drawn `WO-` string** (`J27` caveat e, `J61` boundary d already do). Where a story quotes a number it is that story's fixture label. The same rule holds for a template's `ST-` string (`US-WRK-006` §4) |
| D-17 | `WS-10`/`WS-11` vs the calendar | *Wed 15 Mar 2026* — 15 March 2026 is a **Sunday** | The DATE stands (it is load-bearing across `WO-4822`, `J62`, `J64`, `J65`, `J67`); the day name was typed by hand in the prototype and is DERIVED from the date on every screen. Documents now read *Sun 15 Mar 2026* (`DEF-WRK-3576`, 2026-09-03) |

---

## 6 · What is deliberately NOT modelled

| Not built | Why |
|---|---|
| A parts stock table — on hand, reorder, location | `CR-028` §11-D5 parks it; `OQ-WRK-1490` |
| Tax on a work order — a base flag and a frequency | PO 2026-09-03, *"Dont add Tax on work order - for now"*; B4 §Tax ❄️ |
| Any journal line, any link into Finance | `BR-WRK-004`; `CR-028` D3's precedent; `OQ-WRK-1491` |
| A dispatch batch | *"an entity with no table, no service and no screen"*; `OQ-WRK-1497` |
| A native phone shell | The phone is a web app (`BR-WRK-045`) |
| The EXPORT of a job's photographs, and the pruning job that follows it | ⚠ `OQ-WRK-1496` is **CLOSED** (twelve months, then an export before deletion) — what is not built is the download path, and **nothing may be deleted before it exists**. The period itself is now `BR-WRK-048` and IS written down |
| A second identity for a technician | *"a profile beside an existing identity.User, not a second identity"* |
| A Work-owned copy of areas, certification types, asset types or customers | Read through the seams (`BR-WRK-002`) |
| A `connection` message kind | `OQ-376`, notifications' to add when ruled |
