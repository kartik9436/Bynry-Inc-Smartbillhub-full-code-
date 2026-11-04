# J63 — A rule raises the order, and the Assets door raises another (three exchanges appear overnight reading *Raised by: Asset age rule*, the next night raises none, a clerk on `AST-04412` raises `WO-4908` from the asset — and the Maintenance history's Work order column stops being a dash)

---
id: J63
tier: 2
rules: [BR-WRK-002, BR-WRK-006, BR-WRK-008, BR-WRK-012, BR-WRK-018, BR-WRK-023, BR-WRK-024, BR-WRK-029, BR-WRK-033, BR-WRK-056, BR-SHL-025, BR-TEN-035]
stories: [US-WRK-006, US-WRK-020, US-WRK-037, US-WRK-038]
# ⚠ **NOT ACTIVATED** — no `J63.spec.ts`. At HEAD `work_orders.asset_id` is *"a real,
# migrated, RLS-scoped FK written by nothing"* (`03-field-map.md` §1), there is no
# `work_order_rules` table, no nightly sweep, and the three `WorkOrderR5Checkbox`
# controls on the Assets screens ship DISABLED with a two-word reason (`CR-028` D7).
# Written as the HANDOFF CONTRACT before the code.
# ⚠ STAMP 2026-09-06 (`DEF-WRK-4125`): every sentence above has since landed. CR-070 wave M
# built the table and the nightly sweep, renamed the component to `RaiseWorkOrderCheckbox`,
# and made FOUR ticks live, not three. The paragraph is kept as the record of what was
# true when the contract was written. The journey is still NOT ACTIVATED — that part holds.
#
# `stories:` = `04-flows.md`'s index for `J63` plus `US-WRK-006`, whose frontmatter
# names all eight journeys.
---

**Intent.** Two of the three ways an order comes to exist **without a dispatcher typing
it** (`EP-WRK-07`): a **rule** watching Assets, and a **clerk on an asset**. Both write
through Work's one raise (`create_work_order`, `US-WRK-002`) — Assets writes nothing to
`work_orders` and Work writes nothing to `assets` — and both stamp WHY the order exists,
because *"Raised by is the one nobody asks for until it is missing."* `Work-026` is *"the
riskiest screen on the page: a rule that is on and wrong raises orders all night"*, so
the load-bearing assertions are the negatives: **the same sweep the next night raises
nothing**, **a rule switched Off raises nothing**, and **a meter that already has an
open exchange is not raised again — whoever raised the first one.**

**Upstream leaves.** Tenant **Brazos Bend Utilities** (`brazosbend`). Assets (read
through `assets_seam`): **`AST-04412` · Electric meter · 1φ AMI · installed Mar 2021 ·
`221 Oak Ave · Unit 3` · account `A-10688` · service Electric · certification life ends
Mar 2026** (`assets.certification_due = 2026-03-31`); its Maintenance history: *12 Feb
2026 · Inspection · R. Patel · Annual inspection · 42.00 · Passed · Work order —* and *04
Nov 2025 · Repair · D. Ortiz · Register replaced · 118.00 · Passed · Work order —*.
**Three more electric meters ALREADY PAST their certification life** at the first sweep
(*ours — the flows text says "two more meters past theirs" plus `AST-04412`, but
`AST-04412` is not past life until 31 Mar; three others are needed for the sweep to raise
three*): **`AST-04377` · `88 Willow · A-10901`** (the premises of the dispatcher's
`WO-4830 · Meter exchange · Asset age rule`), **`AST-04385` · `63 Larkspur Ln · A-10777`**
and **`AST-04391` · `9 Fen Close · A-10802`** (*ours*); a fourth, **`AST-04399` · `21
Cedar Ct · A-10884`** (*ours*), whose life ends **3 Mar 2026** (for the Off test). Rules
(`Work-026`), the seven of `WS-26`, six on — the one this journey drives: **Meter
exchange programme · Assets · Meter past certification life · Meter exchange —
residential · Normal · unassigned · This month 184 · On**; the one Off: *Backflow test
due · Assets · lifecycle · Low · 18 · Off*. Template **`ST-0002` Meter exchange —
residential** published at **v2** (7 tasks · 45 min, `J67`'s output; `wot_asset_types`
= *Electric meter · AMI single-phase · Water meter 5/8"–1"*). Priorities Normal = **72
h**. The nightly job `jobs.kind = work.rules_sweep` at **00:30**. Actors: **the system**
(the sweep) · **M. Torres** (the clerk on the asset) · **Alex Reed** (the switch).
Isolation tenant **Lone Star Ridge WSC**, its own seven rules and its own meters, three
of them past life.

**The journey's clock.** Sweep 1: night of **Sat 28 Feb → Sun 1 Mar 2026** (after `J67`
published v2 on the 28th). Sweep 2: **1 → 2 Mar**. Clerk: **Mon 2 Mar 10:15**. Off/On:
**3 → 4 Mar** and **4 → 5 Mar**. Sweep on **31 Mar → 1 Apr**, when `AST-04412` is past
life. Order numbers this journey allocates from the free range: **`WO-4918` · `WO-4919`
· `WO-4920`** (sweep 1), **`WO-4908`** (the clerk, per `04-flows.md`), **`WO-4921`** (the
On test). *The series allocates at raise; a spec asserts order and keys (`J27` caveat e).*

**Where two documents disagreed, and which one this journey follows.**
* `04-flows.md` has the sweep BEFORE the clerk and `AST-04412` among the past-life
  meters; `Work-028` and `US-WRK-038` have the clerk raising on an asset whose life
  *"ends Mar 2026 — the meter-exchange rule **would** raise this on its own"* and whose
  Maintenance history shows **no** order. Both are honoured by the clock above: the
  sweep runs on three OTHER past-life meters first, the clerk raises on `AST-04412`
  before its life ends, and the 1 Apr sweep proves the idempotency covers a person's
  open order. **Filed for the parent** as an ambiguity in the flows text.
* The dispatcher fixture's `WO-4822` (*Meter exchange · 221 Oak Ave · A-10688 · Asset age
  rule*) is, by its premises, an asset-age exchange on `AST-04412` raised on 15 Mar —
  before `WO-4908`'s number and after its date. The r10 `48xx` numbers and the blueprint's
  `49xx` numbers are two fixture generations that do not reconcile; **filed**, and the
  spec asserts keys, not numbers.

| # | Actor · action · screen | Expected outcome (contract — what this step leaves) | Downstream assertions (record · screen · audit · books) | Rule |
|---|---|---|---|---|
| 1 | **Alex Reed** opens **Work › Rules** (`Work-026`) | Seven rows — RULE · SOURCE MODULE · TRIGGER · TEMPLATE RAISED · PRIORITY · THIS MONTH · ENABLED (`StatusPill` On / Off); *Meter exchange programme · Assets · Meter past certification life · Meter exchange — residential · Normal · **184** · On*; `CountFooter` *7 rules · 6 on · Five steps to add one: Trigger · Assignment logic · Notifications · Reminders & escalation · Review & activate*; the `ConsequenceBox` **Audit** — *every rule-raised order carries its source (“Dunning · auto”) so you can trace why it exists* | ⛔ **A rule naming a template in `draft`** (*Leak investigation* before `J62`'s fixture published it) is REFUSED at *Review & activate* — only a published template may be raised; the sentence ≤ 6 words. ✅ `source_module` is one of five (payments · billing · assets · reads · accounts). **The five-step builder is a sub-screen of `Work-026`** (r10 `WRK-13`), no `Work-` id of its own | **BR-WRK-033** · `US-WRK-037` TC-4 |
| 2 | **Sweep 1 — night of 28 Feb → 1 Mar, 00:30.** `jobs.kind = work.rules_sweep` on queue `work` runs *Meter exchange programme* | The engine reads `assets.certification_due < today` **through `assets_seam`** and finds `AST-04377`, `AST-04385`, `AST-04391`. **THREE `work_orders` rows** via `create_work_order`: **`WO-4918`** (`asset_id AST-04377` · `88 Willow · A-10901`) · **`WO-4919`** (`AST-04385`) · **`WO-4920`** (`AST-04391`); each **`source = rule` · `rule_id` = the rule** · `connection_id` NULL · `priority` Normal · **`due_at` = 1 Mar 00:30 + 72 h = 4 Mar 00:30** · `dispatch_state = queued` · assignee NULL · `template_id = ST-0002` · **`template_version = 2`** · its OWN copies (3 safety · 7 tasks · 3 materials · 3 readings · 3 help · details) · `mode = our_crew`. One `jobs` row for the sweep with `raised = 3`; one `audit_log` row per raise, actor *system*, source named | `Work-007` next morning: three new rows reading **RAISED BY *Asset age rule***, Unassigned (the UNASSIGNED tile `4 → 7`); `Work-026`'s THIS MONTH for the rule moves **by three** (`184 → 187` on the February count; the March count starts from these). ✅ `is_gate` FALSE — an exchange gates nothing. ✅ The order's task table has **no FK to `wot_tasks`** — copies, stamped `v2`. ⛔ The engine's read of Payments for *Reconnect after payment* goes through `payments_seam` (read-only); a direct `Payment.objects` import in `apps/work/rules.py` **fails the boundary gate** | **BR-WRK-033** · **BR-WRK-024** · **BR-WRK-008** · **BR-WRK-018** · **BR-WRK-002** · **BR-WRK-023** · `US-WRK-037` TC-1/TC-5 |
| 3 | **Sweep 2 — night of 1 → 2 Mar, 00:30.** The same three meters still qualify | **ZERO new orders.** The sweep's `jobs` row exists with `raised = 0` — a sweep that raised nothing still leaves its record; THIS MONTH unchanged | **A rule is idempotent on (rule, subject, open order)**: a meter with an open exchange is not raised twice. The three orders from step 2 are untouched — no second row, no UPDATE, no re-stamp | **BR-WRK-033** · `US-WRK-037` TC-2 |
| 4 | **The switch (negative).** 3 Mar 09:00 · Alex switches *Meter exchange programme* **Off**; `AST-04399`'s life ends the same day; the sweep runs **3 → 4 Mar** | **Nothing raised** for `AST-04399`; THIS MONTH unchanged; the `enabled` change wrote one `audit_log` row (actor Alex Reed, before/after) | Alex switches it **On** at 09:00 on the 4th; the sweep **4 → 5 Mar** raises **ONE** order for `AST-04399` — **`WO-4921`**, *Raised by: Asset age rule*, `rule_id` set — and nothing for the three that already have one. A rule that is off raises nothing; a rule that is on raises exactly what newly qualifies | **BR-WRK-033** · `US-WRK-037` TC-3 |
| 5 | **Mon 2 Mar 10:15 · M. Torres** opens `AST-04412` and presses **Raise work order** (the action bar) → `Work-028` at `/brazosbend/assets/AST-04412/work-orders/new` | `Panel` THIS ASSET, one `KVLine`: *AST-04412 · Electric meter · 1φ AMI · installed Mar 2021 · **221 Oak Ave · Unit 3** · account **A-10688** · service **Electric*** and *Certification life ends Mar 2026 — the meter-exchange rule would raise this on its own* (the copy carries **no `WM-24`**, B14 rule 32). THE JOB: TEMPLATE picker **lists only templates whose `wot_asset_types` include *Electric meter · 1φ AMI*** — *Meter exchange — residential · Electric · 7 tasks · 45 min* is offered; *Leak investigation* (Water, no asset type) is **not**; PRIORITY Normal · DUE **Mar 31, 2026** · ASSIGN TO *Leave unassigned — the dispatcher will place it* · REASON *Certification life ends. Programmed exchange.* The `ConsequenceBox` **What this writes** reads, in clerk words, *One work order, not tied to a new connection · for this asset · the Maintenance history gains a work-order reference* — **not** the drawn `work_orders` / `connection_id` / `asset_id` / `WM-01` | The route is a **sibling of `…/maintenance/new`** (`S53 · AST-07`) — no new navigation pattern, no new shell; the screen sits in the Assets shell, not Work's. **Nothing is written until the button** | **BR-WRK-056** · **BR-WRK-006** · B14 rules 11, 32 · `US-WRK-038` TC-2 |
| 6 | M. Torres presses **Raise work order ✓** | The SCREEN posts **`POST /work-orders`** (Work's one raise, `US-WRK-002` #14) with `asset_id`. **ONE `work_orders` row — `WO-4908`**: **`asset_id = AST-04412` · `connection_id` NULL** · `source = assets` (*Raised by: Assets*) · Normal · `due_at` 31 Mar 2026 · `dispatch_state = queued` · assignee NULL · `template_id = ST-0002` · `template_version = 2` · `detail` = the reason · its own copies; one `audit_log` row, actor M. Torres | `Work-007` shows `WO-4908 · Meter exchange · 221 Oak Ave · A-10688 · E · Normal · Unassigned · Mar 31 · Queued · **Assets**`. ⛔ The anchor CHECK: a raise naming no connection, premises, account or asset is refused on PostgreSQL before any row exists. ✅ `work_orders.asset_id` — *"the column already exists and nothing writes it today"* — is now written, by Work, from the screen | **BR-WRK-056** · **BR-WRK-006** · **BR-WRK-024** · **BR-WRK-008** · BR-TEN-035 · `US-WRK-038` TC-1 |
| 7 | M. Torres returns to **Asset detail › Maintenance history** for `AST-04412` | The **Work order** column — a dash on every row until now — reads **`WO-4908`** for this asset (the latest `work_orders` row with this `asset_id`, read through the seam) | ⛔ An asset with maintenance rows and **no order** still reads a dash, honestly (`WS-20`). The read is a READ: `apps/assets/**` adds no column and writes nothing — `grep` of `apps/assets/**` for a `work_orders` write = **0**; the door is the screen calling `POST /work-orders` | **BR-WRK-056** · **BR-WRK-002** · `US-WRK-038` TC-4/TC-5 |
| 8 | **Four doors, one form** (`Work-020`): the four `RaiseWorkOrderCheckbox` ticks on Asset add · Asset reassign/move · Asset log maintenance · Asset retire/replacement (`DEF-WRK-4125`) | All four **ENABLED**; their *Work R5* two-word note **gone**; each pre-ticks and posts **the same `Work-028` form on save** | ⛔ **Asset add with *Raise an installation work order* ticked, and the add fails validation → NO order** — the asset saves first, then the raise; a failed asset save raises nothing (one screen transaction, two writes in order). The route pattern matches `AST-07`'s. `WS-26`'s caption: *the four disabled Assets checkboxes at WS-20 and this screen are the same feature* | **BR-WRK-056** · **BR-WRK-033** · `US-WRK-038` TC-3/TC-7 · `US-WRK-037` TC-7 |
| 9 | **Skills, for the exchange the dispatcher will place** (`Work-023`) | D. Ortiz (Meter fitting · Water II · Meter I) and M. Chen appear in the Technician picker for `WO-4908`; **R. Patel (Water I · Reads) is NOT offered** — the template's skill is Meter fitting and *"the skill match is the same test"* for a person, a crew or a contractor | ⛔ Deleting a technician with assigned jobs is refused; *Set unavailable* offered. `Work-023`'s footer *6 rows · 4 people, 1 crew, 1 contractor* | **BR-WRK-028** · **BR-WRK-029** · `US-WRK-020` TC-3/TC-4/TC-5 |
| 10 | **Sweep on 31 Mar → 1 Apr, 00:30.** `AST-04412` is now past its certification life | **Nothing raised for `AST-04412`** — it holds an open exchange, `WO-4908`, raised by a person. The `jobs` row reads `raised = 0` | **The idempotency key is (rule, subject, open order), and the open order need not be the rule's own** — a person's raise is respected, not doubled. The three rule-raised orders and `WO-4921` are likewise not re-raised | **BR-WRK-033** · `US-WRK-037` TC-2 |
| 11 | **Versions, read from the raised orders** (`Work-022` for `ST-0002`) | Usage: the five orders raised in this journey (`WO-4918`–`4921`, `WO-4908`) each stamp **`template_version = 2`**; the Versions tab's ORDERS RAISED for v2 moved by five; the per-version counts sum to the Usage total | **Delete** on `ST-0002` is disabled with its reason and the API refuses — versions are referenced. Editing the template afterwards changes none of the five orders' seven tasks (`BR-WRK-008`, proven in `J67`) | **BR-WRK-012** · **BR-WRK-008** · `US-WRK-018` TC-4/TC-7 |
| 12 | **ISOLATION — Lone Star Ridge WSC** (`app.tenant_id` = Lone Star's) | Its `Work-026` shows **its own seven seeded rules and its own counts**; its three past-life meters raise orders **on Lone Star only** — Brazos Bend's sweep never reads them and Brazos Bend's rule never fires on them; `/lone-star-ridge/assets/AST-04412/work-orders/new` → **`404`**; its Technician picker is its own — D. Ortiz absent | Two tenants' sweeps on the same `work` queue carry two scope keys; neither dedupes the other. Every seam read with `app.tenant_id` unset returns zero rows | hard rule 1 · `US-WRK-037` TC-6 · `US-WRK-038` TC-6 · `US-WRK-020` TC-6 |
| 13 | **INVARIANCE** | — | Five raises, five `audit_log` rows, each with its source (*Asset age rule* ×4, *Assets* ×1) and its actor (*system* ×4, M. Torres ×1). **Zero writes by `apps/work/` to `assets`, and zero by `apps/assets/` to `work_orders`** — the boundary gate passes both ways. No money: nothing here is costed, priced or posted (`BR-WRK-004`); no journal line. `WO-4908`'s number is never renumbered. Every raised order is a copy of `ST-0002 v2` with no link back | **BR-WRK-002** · **BR-WRK-024** · BR-WRK-004 · BR-TEN-035 · hard rule 7 |

**This journey leaves (for downstream).** Four rule-raised orders (`WO-4918`–`WO-4920`,
`WO-4921`) with `source = rule` and `rule_id` set · **`WO-4908`** with `asset_id =
AST-04412`, `connection_id` NULL, `source = assets`, Queued and unassigned · the
Maintenance history's Work order column reading **`WO-4908`** where every row read a
dash · the four `RaiseWorkOrderCheckbox` ticks enabled · THIS MONTH moved by three, then
one · Lone Star Ridge untouched by any of it. **Downstream:** `J62`'s dispatcher places
these; `J67`'s v2 is what they copied.

## Boundaries — what this journey stops at, and why

| # | Not asserted | Because |
|---|---|---|
| a | Whether a rule may ASSIGN as well as raise | Drawn (*Assignment logic*) and built as drawn — a rule that assigns writes an `assign` row like a dispatcher does (`US-WRK-037` §8). Not exercised here: this rule leaves orders unassigned |
| b | The six source modules' triggers other than Assets | Each fires from a module that already ships; only the asset-age trigger is driven here. The Payments trigger's seam boundary is asserted statically in step 2 |
| c | The drawn `WO-` and `AST-` strings | `BR-TEN-035` allocates at raise; `AST-04377`, `AST-04385`, `AST-04391`, `AST-04399` and their premises are this journey's fixture values (*ours*) and should be written once in `US-WRK-006` — reported to the parent |
| d | `WO-4822`'s place in this story | The dispatcher fixture draws it as an asset-age exchange at `AST-04412`'s premises on 15 Mar; the two fixture generations (r10 `48xx`, blueprint `49xx`) do not reconcile — reported, not resolved here |
| e | A dispatch batch number on the sweep's three | **`OQ-WRK-1497`, OPEN, non-blocking** — nothing allocates from `DSP-`; asserted in `J60` step 4 |
