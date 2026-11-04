# 16 · Work — screen layouts

**One entry per screen drawn in §13 *Screens to build*, written while looking at its wireframe**
(`wireframes/Work-0nn.png`, rendered 2026-09-03 from the PDF the Product Owner exported that day). Each
entry names the **frame**, the **template**, the **route**, the **regions top-to-bottom**, the **components**
from `09-component-inventory.md` — and nothing that is not in that inventory — and the commitment cards drawn
on it. **Twenty-one screens are drawn; twelve are not in this file** (the nine that exist today and the three
phone screens) and get a pointer entry so nobody reads a layout that was never seen.

**Where a drawing and B14 — or a PO ruling — disagree, B14 wins and the entry says so.** The closing table
lists every such place. **`Work-031` is drawn and is not built** (PO 2026-09-03: *"Dont add Tax on work order
- for now"*).

**The wireframe's chrome is not the product's.** Every drawing carries a mono *route bar* (the URL on the
left, *signed in · M. Torres* or *step 1 of 8 · nothing saved until Publish* on the right). That bar is the
document's device for showing the route; the product renders the staff shell's own top bar and the step
counter belongs to the wizard frame. Do not build a route bar.

## Templates

| Code | Shape | Used by |
|---|---|---|
| **W1** | `StaffShell` → `PageHead` (kicker · title · optional primary button · **the module tab strip** · one sentence as the tab's explainer) → `Card` (caps header + right control) → `DataTable` → `CountFooter` → `NoteBar` | module lists: Work-013 · 023 · 025 · 026 · 009 |
| **W2** | W1 with `KPIStrip` between the head and the card, `FilterBar` (search + chips) inside the card, bulk checkboxes, and an `ActionRow` under the table | the dispatcher: Work-007 |
| **W3** | wizard frame → `Kicker` → question `Title` → sentence → `Stepper` → `Panel`s → `ConsequenceBox` → `ButtonRow` (← Back · Continue → · Save draft) → `NoteBar` | Work-014 · 015 · 016 · 017 · 029 |
| **W4** | `Kicker` → `Title` + meta line → `Tabs` → `Panel`s (checklists, a readings table, contacts) → `ConsequenceBox` → `ButtonRow` with a danger commit | the order detail: Work-008 · 033 |
| **W5** | `Kicker` → `Title` + meta + `StatusPill` → `ActionRow` (edit · duplicate · deactivate · delete-disabled) → `Tabs` → `Card` table → `CountFooter` → `NoteBar` | record detail: Work-022 · 024 |
| **W6** | `Kicker` → `Title` → sentence → `Panel`s of `FormField`s (each with its allowed-values help line) → `ConsequenceBox` (*Change effects* / *What this writes*) → `ButtonRow` (Cancel · danger · primary ✓) | edit / raise forms: Work-021 · 028 |
| **W7** | `Kicker` (SETTINGS › …) → `Title` → sentence → `Card` (caps header + right meta) → `DataTable` with money at 4 dp → mono footnote → `ConsequenceBox` → `NoteBar` | settings lists: Work-030 · (031, not built) |
| **W8** | `Document`: utility kicker → title → meta → caps `Section`s (outcome · tasks · readings and photographs · cost · customer) → `NoteBar` | the report: Work-032 |
| **W9** | W1 with a four-tile `KPIStrip` and a table ending in a `TotalRow`, then a `ConsequenceBox` | performance: Work-027 |

`WorkTabs` is the module's own strip — **Orders · Map · Crews · Parts · Templates · Rules**, plus **Awaiting
approval** (drawn second on Work-009) and **Performance** (drawn last on Work-027). One strip, eight tabs;
the drawing shows six or seven at a time because each frame is cropped to what it needs.

⚠ **`WorkTabs` IS NOT A COMPONENT ANY MORE — IT IS THE SHARED PAGE HEADER'S TAB STRIP (2026-09-05,
`DEF-WRK-3955`).** Every drawing in this pack draws a BOXED folder tab — a border on three sides, the page
colour behind the active one — sitting ABOVE the page head. The module built exactly that, and the Product
Owner put it beside Payments and said: *"work - tabs does not match with our UI rules - ensure you follow
all UI rules for Work UI/screen while Ui is build as per images you ahev taken"*.

**B14 rule 36 is where the line falls, in the PO's own words the day before:** *"UI screens layout and
details you can folow from Screens that we capture from document, but style guide should be from r10
agreement"*. A tab's SHAPE and where it sits relative to the title are style, so the kit wins; the tab SET,
its order and its labels are layout, so this pack still wins. Nothing about which tabs exist changed.

So the strip is `components/PageHeader.tsx`'s — underlined, accent-coloured, below the H1 — and each Work
screen declares it on its own header (`useWorkTabs()`), which is also what B14 rule 2 asks for: ONE page
header per screen, and the header is the thing that draws a strip. Read every `W1`/`W2`/`W9` row below as
`StaffShell → PageHead (kicker · title · **tabs** · one sentence)` rather than `StaffShell → WorkTabs →
PageHead`. `r10`'s own `UI-RULES.md` says nothing about tabs at all, so the authority here is the kit —
the eight other features that already compose it — and not a written rule.

---

## 13.1 · Creating a template — Work-013 … 017

### `Work-013` · Work · Templates — the list · `wireframes/Work-013.png`
**Frame:** `StaffShell` → `WorkTabs` (Templates active) · **Template:** W1 · **Route:** `/{tenant}/work/templates`
**Regions:** kicker *WORK* · title *Work order templates* · one sentence (*The jobs each service needs, written down once. Every work order you raise is a copy of one of these.*) · **+ New template** (secondary outline) · `Card` *YOUR TEMPLATES* with **Filter by service ▾** at right · `DataTable` — TEMPLATE · SERVICE · JOB TYPE · CONTENTS (*2 tasks · 0 parts · 1 reading*) · GATE (*Meter set* with a red flag) · SKILL · EST. · STATUS (`StatusPill` Published / Draft / Inactive) · ACTIONS (pencil icon) · `CountFooter` *6 templates · 4 published · 1 draft · 1 inactive  Seeded starters are marked and can be edited or deleted.* · `NoteBar` on the unique key.
**Components:** PageHead · Button.secondary · Card · DataTable · StatusPill · IconAction · CountFooter · NoteBar.
**Drawn on it:** `WM-08` (the relaxed unique key: two Water templates in one list).
**Deviation:** CR-045's toolbar standard puts one search, one filter set and one download glyph on every list — the drawing shows the filter only; **build the toolbar to the standard.**

### `Work-014` · New template · step 1 of 8 — Details · `wireframes/Work-014.png`
**Frame:** wizard frame (step counter *step 1 of 8 · nothing saved until Publish*) · **Template:** W3 · **Route:** `…/work/templates/new?step=1`
**Regions:** kicker *WORK › TEMPLATES* · title *What job is this template for?* · one sentence · `Stepper` of eight (*1 Details · 2 Safety · 3 Tasks · 4 Materials · 5 Readings · 6 Help & support · 7 Signature · 8 Review*) · `Panel` *START FROM A PACK* — four `PackCard`s in a row (*Meter exchange · 7 tasks · 3 parts · 3 readings* · *New connection* · *Inspection* · **Start empty**) · `Panel` *THIS TEMPLATE* — `FormField`s NAME · SERVICE · JOB TYPE (help line *From the job type catalogue*) · APPLIES TO ASSET TYPES (chips) · SKILL NEEDED · CREW SIZE · SAFETY KIT · `Panel` *WHAT THE TECHNICIAN SEES ON THE JOB* — four checkboxes in two rows · `ButtonRow` **← Back** (disabled) · **Continue →** (primary outline) · **Save draft** · `NoteBar` *Step 1 of 8 · nothing is saved to a work order until you Publish…*
**Components:** Stepper · PackCard · Panel · FormField · CheckRow · ButtonRow · NoteBar.
**Drawn on it:** `WM-11` (the eight-step builder); rests on `WM-08`, `WM-09`, `WM-04`, `WM-06`.
**Deviation:** the help line names `WM-04` — a rule id in clerk copy; **rule 32 strips it** (*From the job type catalogue* stands alone).

### `Work-015` · New template · step 3 of 8 — Tasks · `wireframes/Work-015.png`
**Frame / Template / Route:** wizard · W3 · `…/new?step=3`
**Regions:** kicker *WORK › TEMPLATES › METER EXCHANGE — RESIDENTIAL* · title *What are the steps?* · sentence (*In the order a technician does them. Each one appears as a tick box on the phone.*) · `Stepper` (3 active) · `Panel` *TASKS — 7 STEPS · 45 MIN TOTAL* — `EditableTable`: drag handle ≡ · # · TASK · MINUTES · PHOTO (`StatusPill.red` *Required* or —) · MUST DO · ✕ remove; **inline add row** *Add a task…* · *Minutes* · **📷 Photo** · **+ Add** · `ConsequenceBox` *45 minutes total is what the dispatcher sees when scheduling. Estimates that are wrong here make every day's route wrong.* · `ButtonRow`.
**Components:** EditableTable (DragHandle · InlineAddRow) · StatusPill · ConsequenceBox.
**Drawn on it:** `WM-09` (seven child tables — `wot_tasks`).

### `Work-016` · New template · step 5 of 8 — Readings · `wireframes/Work-016.png`
**Frame / Template / Route:** wizard · W3 · `…/new?step=5`
**Regions:** kicker · title *What has to be measured?* · sentence (*Each reading has an accepted range. An out-of-range entry flags on the phone and on the completed order — it is never refused.*) · `Stepper` (5) · `Panel` *READINGS — 3* — `EditableTable`: ≡ · PROMPT · UNIT · MIN · MAX · PHOTO (*Required* / *Optional*) · REQUIRED · BECOMES A METER READ (`StatusPill.green` *Yes — posts on approval* / `StatusPill.grey` *No — recorded only*) · ✕; inline add row *Prompt…* · *Unit* · *Min* · *Max* · **+ Add** · `ConsequenceBox` on *Becomes a meter read* · `ButtonRow`.
**Components:** EditableTable · StatusPill · ConsequenceBox.
**Drawn on it:** `WM-29` (readings that post as meter reads). **Hard rule 3 on screen:** the unit is a column, never a word in the prompt.

### `Work-017` · New template · step 8 of 8 — Review and publish · `wireframes/Work-017.png`
**Frame / Template / Route:** wizard (*step 8 of 8 · ready to publish*) · W3 · `…/new?step=8`
**Regions:** kicker · title *Review* · sentence · `Stepper` (8) · `Panel` *METER EXCHANGE — RESIDENTIAL · ELECTRIC · 7 SECTIONS · 26 ITEMS* — `DataTable` SECTION · ITEMS · WHAT IT PRODUCES ON THE JOB · pencil (Details 4 · Safety 3 **Blocks the task list until all three are ticked** · Tasks 7 · Materials 3 · Readings 3 · Help & support 3 · Signature 3) · `ConsequenceBox` *Publishing affects **new** work orders only. The 4 orders already raised from the previous version keep exactly what they were given — nothing in the field changes.* · `ButtonRow` **← Back** · **Publish template** (primary) · **Save as draft** · **Delete** (danger, disabled) · `NoteBar` *Delete is disabled because this template has produced work orders. Deactivate it instead…*
**Components:** DataTable · ConsequenceBox · Button.danger (disabled) · NoteBar.
**Drawn on it:** `WM-10` (the write service — publish is the one write).

## 13.2 · Running the work — Work-007 · 008 · 009

### `Work-007` · Work · Orders — the dispatcher · `wireframes/Work-007.png`
**Frame:** `StaffShell` → `WorkTabs` (Orders active) · **Template:** W2 · **Route:** `/{tenant}/work/orders`
**Regions:** kicker *WORK* · title *Work orders* · sentence (*Everything open, across every connection and every account.*) · `KPIStrip` of **five** `KpiTile`s — UNASSIGNED **4** *nobody is going* · DUE TODAY **5** *2 of them urgent* · IN THE FIELD **2** *en route or on site* · AWAITING APPROVAL **3** *field done, nobody accepted* · OVERDUE **1** *WO-4823 · 2 days* · `Card` *OPEN ORDERS* with **Columns ▾** at right · `FilterBar` — search *Search WO #, premise…* + chips *Type · all · Status · all · Priority · all · Technician · all · Area · all* · `DataTable` with bulk checkbox — ORDER · TYPE · PREMISE (*903 Birch Ln · A-10222*) · SVC · PRIORITY (`PriorityPill` Urgent red / High amber / Normal grey / Low grey) · TECHNICIAN (`StatusPill.red` *Unassigned* when none) · DUE · STATUS (`StatusPill` On site teal / En route teal / Queued grey / Scheduled green) · RAISED BY (*Payment received · Dispatcher · Dunning · auto · High-usage alert · Asset age rule · Compliance calendar · Billing exception*) · `CountFooter` *Showing 8 of 10 open orders · sorted by priority then due time  1–8 of 10* · `ActionRow` **+ New work order** (secondary outline) · **Assign selected…** · **Reschedule selected…** · **Change priority…**
**Components:** KPIStrip · Card · FilterBar · DataTable (bulk select) · PriorityPill · StatusPill · CountFooter · ActionRow.
**Drawn on it:** `WM-17` (KPI strip, filter bar, ten-column table, bulk select).
**Deviation:** no download glyph — **CR-045 adds it**. The staff `KPIStrip` has carried four tiles; this one needs five — a count, not a new component.

### `Work-008` · Work · Order detail · Checklist · `wireframes/Work-008.png`
**Frame:** `StaffShell` · **Template:** W4 · **Route:** `…/work/orders/WO-4822?tab=checklist`
**Regions:** kicker *WORK › ORDERS* · title *WO-4822 · Meter exchange* · meta line *221 Oak Ave · A-10688 · North · Route 1 · Normal · D. Ortiz · Today 15:30 · Scheduled* · `Tabs` **Overview · Checklist · Parts · Location · Customer · Audit** (Checklist active) · `Panel` *SAFETY — BEFORE YOU START* — three ☐ rows · `Panel` *TASKS — 7 STEPS · 45 MIN ESTIMATED* — seven `CheckRow`s, ticked ones ☑, meta *· 3 min* or *· photo required* in red · `Panel` *READINGS TO TAKE* — `DataTable` READING · UNIT · RANGE · PHOTO REQUIRED (`StatusPill.red` Required / grey Optional) · VALUE (*48,221* / *not taken*) · PHOTOGRAPH CAPTURED (`Thumbnail` ▣ IMG-8841 · 15:12 / — / *not required*) · `Panel` *HELP & SUPPORT* — `ContactRow`s (📄 *Meter exchange SOP v4 (PDF)* · ☎ *Supervisor · M. Torres · (512) 555-0138* · ☎ *AMI activation hotline · ext 44*) · `ConsequenceBox` *Marking complete sends it for approval. It does not activate anything until a person accepts it.* · `ButtonRow` **Mark complete** (primary, disabled until ticks) · **Reassign…** · **Put on hold…** · **Cancel order** (danger).
**Components:** Tabs · Panel · CheckRow · DataTable · StatusPill · Thumbnail · ContactRow · ConsequenceBox · Button.danger.
**Drawn on it:** `WM-19` (the six-tab detail); rests on `WM-09`, `WM-18`, `WM-30`, `WM-29`.

### `Work-009` · Work · Awaiting approval · `wireframes/Work-009.png`
**Frame:** `StaffShell` → `WorkTabs` (**Awaiting approval** active, drawn second) · **Template:** W1 · **Route:** `…/work/awaiting-approval`
**Regions:** kicker *WORK* · title *Awaiting approval* · sentence (*The field has finished these. Nobody has accepted them yet.*) · `DataTable` — ORDER (*WO-4906 · Meter set*) · CONNECTION · PREMISE · SERVICE · OUTCOME (`StatusPill.green` Passed / amber *Partially done*) · COMPLETED · WAITING (*6 days*) · ACTIONS (eye icon) · `CountFooter` *3 orders · oldest waiting 6 days* · `NoteBar` *Every order here has field data and no accepted_by. Accepting one activates its service and tells the customer.*
**Components:** PageHead · DataTable · StatusPill · IconAction · CountFooter · NoteBar.
**Drawn on it:** `WM-03` (one query, no new table).
**Deviation:** the note bar names a column (`accepted_by`) — **rule 32: no internal code in clerk copy**; write *nobody has accepted them*.

## 13.3 · The seven r10 surfaces — Work-021 … 027

### `Work-021` · Work order · Edit — assign, reschedule, cancel · `wireframes/Work-021.png`
**Frame:** `StaffShell` · **Template:** W6 · **Route:** `…/work/orders/WO-4821/edit`
**Regions:** kicker *WO-4821 · DISCONNECT FOR NON-PAYMENT* · title *Edit work order* · sentence (*Everything a dispatcher changes after the order exists.*) · `Panel` *STATUS, PRIORITY AND PROMISE* — STATUS (help line *Queued · Scheduled · En route · On site · Complete · On hold · Cancelled*) · PRIORITY · SLA TARGET · `Panel` *WHO AND WHEN* — ASSIGNED TO (*D. Ortiz · Water II*) · DATE · WINDOW (help *Any time · 08:00–12:00 · 12:00–17:00 · Exact appointment*) · AREA · SUB-AREA · TEMPLATE (*Disconnect — non-payment · 5 steps*) · NOTES FOR THE TECHNICIAN · `ConsequenceBox` **Change effects** — *Customer notification — sent on save if the date or window changes · Technician phone — job updates immediately · Audit — every field change is logged with who and when* · `ButtonRow` **Cancel** · **Cancel work order** (danger) · **Save changes ✓** (primary).
**Components:** Panel · FormField (with allowed-values help line) · ConsequenceBox · Button.danger · Button.primary.
**Drawn on it:** `WM-39`; rests on `WM-14`, `WM-13`, `WM-25`.

### `Work-022` · Template detail — Overview · Usage · Versions · Audit · `wireframes/Work-022.png`
**Frame:** `StaffShell` · **Template:** W5 · **Route:** `…/work/templates/ST-0002`
**Regions:** kicker *SERVICE TEMPLATE · METER WORK · V2* · title *Meter exchange — residential* · meta *40 min · 1 technician ·* `StatusPill.green` *Active* · `ActionRow` **Edit template** (primary outline) · **Duplicate** · **Deactivate** · **Delete** (danger, disabled) · `Tabs` **Overview · Usage · Versions · Audit** (Versions active) · `Card` *VERSIONS* — `DataTable` VERSION (**v2** / v1) · PUBLISHED · BY · WHAT CHANGED (*Added Apply tamper seal; opening-read max 999 → 999*) · ORDERS RAISED (31 / 4) · STATUS (`StatusPill.green` Current / grey Superseded) · `CountFooter` *35 orders raised across 2 versions  The 4 v1 orders still read v1 — nothing was rewritten* · `NoteBar` *Delete is disabled while any order references any version. Deactivate stops new orders and leaves the 35 readable.*
**Components:** ActionRow · Tabs · Card · DataTable · StatusPill · CountFooter · NoteBar.
**Drawn on it:** `WM-40` (versions, and what v2 means).

### `Work-023` · Work · Crews — the list and the certification watch · `wireframes/Work-023.png`
**Frame:** `StaffShell` → `WorkTabs` (Crews) · **Template:** W1 · **Route:** `…/work/crews`
**Regions:** kicker *WORK* · title *Crews* · sentence (*Who can do what, and who is available. Dispatch only offers a technician whose skills match the template.*) · `Card` *TECHNICIANS* with search *Search technicians, skills…* at right · `DataTable` — TECHNICIAN (name; `StatusPill.amber` *cert expiring* inline on J. Kaur) · ROLE · SKILLS (*Water II · Meter I*) · CERTIFICATIONS · SHIFT · TODAY · UTILISATION (*82%*) · STATUS (`StatusPill.green` On shift / teal Off today / grey Contractor) · `CountFooter` *6 rows · 4 people, 1 crew, 1 contractor* · `ConsequenceBox` **Certification watch** — *30 days — J. Kaur, confined space expires Aug 20. **She is blocked from 4 template types until renewed.** · 60 days — M. Chen, HV awareness expires Sep 2026.* · `NoteBar` *A crew and a contractor are rows in the same table as a person…*
**Components:** Card · DataTable · StatusPill · CountFooter · ConsequenceBox · NoteBar.
**Drawn on it:** `WM-21` (also builds Work-024).
**Deviation — RESOLVED 2026-09-04, and the answer is NEITHER the drawing nor the card.** The *blocked from 4 template types* sentence contradicted `WM-21` (*refusing a job on a lapsed one is out of scope*); the Product Owner ruled option (c), ***"per-tenant, default warn"***. **Both sides are built** and `work_settings.certification_lapse_policy` picks one; a new tenant starts at *warn*, so the sentence is **not rendered** on a default utility and IS rendered where a safety officer has switched blocking on. A screen may not claim a guarantee the setting has switched off (hard-won law 1).
**Deviation — TODAY and UTILISATION are NOT drawn (wave F, 2026-09-05).** Both are *jobs belonging to this row*, and `work_orders` has no `assignee_technician_id` or `est_duration` until wave `G` (`03-field-map.md` §3 rows 6–15). A cell that can never carry a real value is dead UI whether it renders a dash or an invented figure — the same call `Work-002`'s TECHNICIAN column already got, for the same reason. Six columns are built: TECHNICIAN · ROLE · SKILLS · CERTIFICATIONS · SHIFT · STATUS.
**Deviation — the *add a technician* control on the empty state is DISABLED WITH ITS REASON** (`BR-SHL-025`): a technician is a profile beside a login and the login is created in Settings → Team, so the flow starts there.

### `Work-024` · Technician detail — Overview · Jobs · Certifications · Audit · `wireframes/Work-024.png`
**Frame:** `StaffShell` · **Template:** W5 · **Route:** `…/work/crews/r-patel`
**Regions:** kicker *TECHNICIAN · SENIOR TECHNICIAN* · title *R. Patel* · meta *Water I · Reads · shift 07:00–16:00 · 5 jobs today ·* `StatusPill.green` *On shift* · `ActionRow` **Assign skills** (primary outline) · **Set unavailable** · `Tabs` **Overview · Jobs · Certifications · Audit** · `Panel` *SKILLS & PROFICIENCY* — `DataTable` SKILL · PROFICIENCY (*Certified · Trained · Not held*) · MAKES THEM ELIGIBLE FOR · `Panel` *CERTIFICATIONS* — `ChipRow` *Backflow tester* `exp Jan 2028` · *First aid / CPR* `exp Sep 2027` · `Panel` *THIS MONTH* — inline figures *Jobs closed **88** · First-visit completion **92%** · Avg vs estimate **−4 min*** · `NoteBar` *Shift 07:00–16:00 Mon–Fri · Routes: Route 3 · North district · Van: Unit 12 (26 parts on board).*
**Components:** ActionRow · Tabs · Panel · DataTable · ChipRow · InlineFigures · NoteBar.
**Drawn on it:** `WM-21` (card under Work-023); rests on `WM-13`, `WM-41`, `WM-31`.
**Deviation — the *THIS MONTH* panel is NOT drawn, and two of the four tabs are not either (wave F, 2026-09-05).** *Jobs closed **88** · First-visit completion **92%** · Avg vs estimate **−4 min*** are all *jobs belonging to this person*, which needs wave `G`'s assignee column; the **Jobs** tab needs the same column and **Audit** needs wave `M`'s trail reader. Neither tab is drawn rather than drawn-and-disabled — `WorkShell.tsx` states the module's rule (*"a tab for a screen that does not exist would be a control onto nothing"*), and `DEF-CWP-3925` is what a hold costs when the screen behind it lands and nobody greps for the control. **Overview and Certifications ship.**
**Deviation — the skills wizard's step 1 CONFIRMS the technician rather than picking one.** `WS-24`'s card names the steps *Select technician · Skills & certifications · Confirm & update*; the wizard is reached from one person's own screen, and a picker there would let a supervisor open R. Patel and edit M. Chen. **Certifications are not edited in it either** — an expiry date belongs on a form of its own, and `PUT …/certifications` exists for the screen that is owed.

### `Work-025` · Work · Parts — stock register and issue log · `wireframes/Work-025.png`
**Frame:** `StaffShell` → `WorkTabs` (Parts) · **Template:** W1 with a `SegmentedControl` · **Route:** `…/work/parts`
**Regions:** kicker *WORK* · title *Parts* · sentence (*A system of record — what you own, where it sits, and who took it.*) · `SegmentedControl` **Stock register** | Issue log · `ConsequenceBox` **Reorder** — *2 parts at or below reorder level. Roughly 320 units needed to restore cover.* · `Card` *STOCK REGISTER* — `DataTable` PART # · DESCRIPTION · CATEGORY · LOCATION (*Yard · Van 12*) · ON HAND · REORDER AT · UNIT COST (*78.40*) · STATUS (`StatusPill.green` In cover / red Below reorder / amber At reorder) · `CountFooter` *Same part in two locations is two rows  Imports merge on part # + location* · `Card` *ISSUE LOG* with **− Issue parts** · **+ Return entry** at right — `DataTable` DATE · PART · QTY (*−2 · +4*) · ISSUED TO · PURPOSE (*Exchanges on Route 2 (ref WO-4821)*) · RECORDED BY · `NoteBar` *Issues deduct stock the moment they are recorded. The work-order reference is plain text…*
**Components:** SegmentedControl · ConsequenceBox · Card · DataTable · StatusPill · CountFooter · NoteBar.
**Drawn on it:** `WM-22` (parts against a job).
**Deviation — the drawing contradicts its own card:** ON HAND · REORDER AT · the In-cover/Below-reorder status and *Issues deduct stock* are stock levels, and `WM-22` says *"No stock decrement; stock levels are out of scope"* (`CR-028` D5). **The card wins:** the register, the issue log and the issue-against-a-job flow are built; **the three stock columns, the status pill and the reorder box are held** until the Work lane's parts-stock question is ruled.

### `Work-026` · Work · Rules — what raises an order without a person · `wireframes/Work-026.png`
**Frame:** `StaffShell` → `WorkTabs` (Rules) · **Template:** W1 · **Route:** `…/work/rules`
**Regions:** kicker *WORK* · title *Rules* · sentence (*Rules watch the rest of SMARTBillHub and raise work orders on their own.*) · **+ New rule** (secondary outline) · `DataTable` — RULE · SOURCE MODULE (*Payments · dunning*) · TRIGGER (*Final notice expires unpaid*) · TEMPLATE RAISED · PRIORITY · THIS MONTH (*96*) · ENABLED (`StatusPill.green` On / grey Off) · `CountFooter` *7 rules · 6 on  Five steps to add one: Trigger · Assignment logic · Notifications · Reminders & escalation · Review & activate* · `ConsequenceBox` **Audit** — *every rule-raised order carries its source (“Dunning · auto”) so you can trace why it exists.*
**Components:** PageHead · Button.secondary · DataTable · StatusPill · CountFooter · ConsequenceBox.
**Drawn on it:** `WM-24` (rules that raise work orders on their own; the five-step builder is a sub-screen of this one).

### `Work-027` · Work · Performance — did the field keep its promises · `wireframes/Work-027.png`
**Frame:** `StaffShell` → `WorkTabs` (**Performance** active, drawn last) · **Template:** W9 · **Route:** `…/work/performance`
**Regions:** kicker *WORK* · title *Performance* · sentence (*Whether field work is keeping its promises — and what it costs to keep them.*) · `KPIStrip` of four — SLA MET **94.2%** *↑ 2.1pt month on month* (lead tile, teal) · FIRST-TIME FIX **88%** · COST PER JOB **$74** *labour + parts + travel* · RECONNECT TIME **2h 40m** *payment to service restored* · `Card` *BY JOB TYPE* — `DataTable` JOB TYPE · VOLUME · AVG DURATION · SLA MET · FIRST-TIME FIX · COST / JOB · TOTAL COST, ending in `TotalRow` **Total field cost · 740 · — · — · — · — · $56,337** · `ConsequenceBox` *r10 says this total “feeds the O&M / labour line in Finance → Cost & Margin.” **Do not build that link.** CR-028 D3…*
**Components:** KPIStrip (lead tile) · Card · DataTable · TotalRow · ConsequenceBox.
**Drawn on it:** `WM-41`. The Finance arrow is refused by the drawing itself; the consequence box's `CR-028 D3` is a rule id in clerk copy — **rule 32 strips the id and keeps the sentence.**

## 13.4 · Doors, rates, tax, report — Work-028 … 033

### `Work-028` · Assets › Asset detail › Raise work order · `wireframes/Work-028.png`
**Frame:** `StaffShell` (Assets, not Work) · **Template:** W6 · **Route:** `/{tenant}/assets/AST-04412/work-orders/new` — a sibling of `…/maintenance/new` (S53 · AST-07)
**Regions:** kicker *ASSETS › AST-04412 · ELECTRIC METER · 1Φ AMI* · title *Raise a work order for this asset* · sentence (*The asset, its premise and its account are already known. You are choosing the job.*) · `Panel` *THIS ASSET* — one `KVLine` (*AST-04412 · Electric meter · 1φ AMI · installed Mar 2021 · **221 Oak Ave · Unit 3** · account **A-10688** · service **Electric*** and *Certification life ends Mar 2026 — the meter-exchange rule would raise this on its own.*) · `Panel` *THE JOB* — TEMPLATE (*Meter exchange — residential · Electric · 7 tasks · 45 min*; help *Filtered to templates whose applies to asset types includes this asset's type*) · PRIORITY · DUE · ASSIGN TO (*Leave unassigned — the dispatcher will place it*) · REASON · `ConsequenceBox` **What this writes** — *One work_orders row, **not** connected to a build · asset = AST-04412 · The Maintenance history Work order column stops being a dash for this asset* · `ButtonRow` **Cancel** · **Raise work order ✓** (primary) · `NoteBar` **Four doors, one form.** *Asset detail's action bar · the Maintenance history panel · and the three checkboxes that ship disabled today on Asset add, Asset retire and Asset move…*
**Components:** Panel · KVLine · FormField · ConsequenceBox · Button.primary · NoteBar.
**Drawn on it:** `WM-43` (the Assets door — one form, four ways in).
**Deviation:** the consequence box names `work_orders`, `connection_id`, `asset_id` and `WM-01` — **rule 32**: the clerk reads *One work order, not tied to a new connection · for this asset · the Maintenance history gains a work-order reference*.

### `Work-029` · Accounts › Move-out › Field visit — raising the job from Customers · `wireframes/Work-029.png`
**Frame:** the move-out wizard (Customers) · **Template:** W3 (*step 4 of 6 · nothing is written until step 6*) · **Route:** `/{tenant}/accounts/A-10688/move-out?step=4`
**Regions:** kicker *ACCOUNTS › A-10688 · MILLER, SARAH* · title *Does somebody have to attend?* · sentence (*A move-out usually needs a final read, and sometimes a disconnection at the curb.*) · `Panel` *FIELD VISIT* — three `CheckRow`s: ☑ **Raise a work order for the final read** *— Electric · Final read & deactivate · due **28 Mar 2026*** (drawn *de-energise*; `CR-032` — `DEF-WRK-3578`) · ☐ *Raise a work order to lock the water curb stop — Water · Disconnect at curb* · ☐ *No visit needed — the customer will send a photo of the meter* · `Panel` *WHAT HAPPENS ON SAVE* — `DataTable` # · ACT · MODULE · RESULT (*1 Close the account, settle the deposit, cut the final bill · Customers · as today* / *2 **The screen calls metering** to raise the work order · Work · WO-4907 · Queued · unassigned* / *3 The order carries its source · Work · Move-out · A-10688*) · `ConsequenceBox` **The move-out does not wait for the visit, and the visit does not close the account.** … · `ButtonRow` **← Back** · **Continue →** (primary).
**Components:** Panel · CheckRow · DataTable · ConsequenceBox · ButtonRow.
**Drawn on it:** `WM-44` (two calls from one wizard step, never a cross-module write). *No visit needed* is a recorded choice, not an unticked box.

### `Work-030` · Settings › Work › Labour rates · `wireframes/Work-030.png`
**Frame:** Settings (reference data) · **Template:** W7 · **Route:** `…/settings/configure/reference-data/work-labour-rates`
**Regions:** kicker *SETTINGS › CONFIGURE › REFERENCE DATA › WORK* · title *Labour rates* · sentence (*What an hour in the field costs. Used to price a job and to total the performance tab.*) · `Card` *RATES BY ROLE* with **Effective 01 Jan 2026** at right · `DataTable` ROLE · PER HOUR (*48.5000*) · OVERTIME / HOUR · OVERTIME STARTS AFTER (*8 h / day* or —) · EFFECTIVE FROM (*01 Jan 2026* / *01 Jan 2025 — superseded*) · ACTIONS (pencil; eye on the superseded row) · mono footnote *Displayed to 2 decimals on every screen that shows money to a customer  Stored to 4* · `ConsequenceBox` **A rate is dated, and a job keeps the rate it was closed at.** … · `NoteBar` on contractors carrying one rate.
**Components:** Card · DataTable (MoneyCell at 4 dp here — a settings screen, hard rule 2) · IconAction · ConsequenceBox · NoteBar.
**Drawn on it:** `WM-45`. The 4-dp display is deliberate on THIS screen (it is the stored value being edited); every customer-facing screen shows 2.

### `Work-031` · Settings › Work › Taxes that apply to a work order · `wireframes/Work-031.png` — **NOT BUILT**
**PO ruling 2026-09-03:** *"Dont add Tax on work order - for now"*. The drawing (W7: kicker *SETTINGS › TAXES & FEES* · title *Taxes that apply to field work* · a `DataTable` TAX · JURISDICTION · FORM · RATE (*0.062500*) · BASE (**labour + parts**) · APPLIES TO · a `ConsequenceBox` *The gap is one flag, not one table*) is kept as the record of what was proposed. **Nothing on it is specified for build**; `WM-46` adds a third base to the frozen tax rule and goes through the finance re-sign path, not a lane. The report (`Work-032`) shows no tax lines until then.

### `Work-032` · The work order report — generated on approval · `wireframes/Work-032.png`
**Frame:** `Document` (a PDF, not a screen) · **Template:** W8 · **Route:** `…/work/orders/WO-4822/report.pdf` (*generated 15 Mar 2026 16:41 · WO-4822-v1*)
**Regions:** kicker *BRAZOS BEND UTILITIES* · title *Work order WO-4822 · Meter exchange — residential* · meta *221 Oak Ave · Unit 3 · account A-10688 · Miller, Sarah · Electric* · `Section` *OUTCOME* — *Completed **15 Mar 2026 16:07** by **D. Ortiz** · outcome* `StatusPill.green` *Passed* *· approved **16 Mar 2026 09:12** by **M. Torres*** / *On site 15:15 – 16:07 · **52 min** worked against a **45 min** estimate* · `Section` *TASKS · 7 OF 7* — seven ☑ rows with values (*48,221 kWh · 📷*; *1,204 kWh* **out of range 0–999 · flagged** · 📷; *seal 4417882*) · `Section` *READINGS AND PHOTOGRAPHS* — `DataTable` READING · VALUE · UNIT · IN RANGE (`StatusPill.green` yes / red *no · 0–999*) · PHOTOGRAPH (`Thumbnail` ▣ IMG-8841 · 15 Mar 15:12) · `Section` *COST* — `DataTable` LINE · QTY · RATE · AMOUNT (*Labour · Field technician · 0.87 h · 48.5000 · 42.20* / *Part · MTR-E1P … · 1 · 96.0000 · 96.00* / *Part · SEAL-01 · 1 · 0.2200 · 0.22* / *State sales tax · 6.25% · — · 0.062500 · 8.65* / *City sales tax · 2.00% · 2.77*) ending in `TotalRow` **Total 149.84** · `Section` *CUSTOMER* — *Signed **S. Miller** · 15 Mar 2026 16:07 · signature image SIG-4822* / *Technician's note: “Customer present throughout. Old meter left for collection.”* · `NoteBar` *Generated once, on approval, and frozen. A later correction produces **WO-4822-v2** beside it; neither is overwritten.*
**Components:** Document · Section · CheckRow · DataTable · StatusPill · Thumbnail · MoneyCell · TotalRow · NoteBar.
**Drawn on it:** `WM-47` (the report), `WM-48` (three document kinds).
**Deviations:** **the two tax lines and the $149.84 total are not built** (PO ruling on `WM-46`); until tax is ruled the COST section ends at the labour-plus-parts total **$138.42**, computed in one named function (0.87 h × 48.5000 = 42.195 → 42.20, hard rule 2). Rate shows 4 dp on the report as drawn — **the report is customer-facing, so rule 2 displays 2**: *48.50*.

### `Work-033` · Work order detail › Readings — the photograph that came back · `wireframes/Work-033.png`
**Frame:** `StaffShell` · **Template:** W4 (the Readings panel of the Checklist tab, drawn on its own) · **Route:** `…/work/orders/WO-4822?tab=checklist`
**Regions:** kicker *WO-4822 · METER EXCHANGE — RESIDENTIAL* · title *Readings to take* · sentence (*What the template asked for, and what the phone sent back.*) · `Card` *READINGS* — `DataTable` READING · UNIT · RANGE · PHOTO REQUIRED (`StatusPill.red` Required / grey Optional) · VALUE (*48,221* / *1,204* **out of range** in red / *E1P-77412* / *not taken*) · PHOTOGRAPH CAPTURED (`Thumbnail` ▣ IMG-8841 · D. Ortiz · 15:12 / *none — not required* / `StatusPill.amber` **missing — job cannot close**) · `CountFooter` *3 of 4 readings captured · 2 of 3 required photographs  Click a thumbnail for the full image, taken at, and device* · `ConsequenceBox` **Required means the job will not close without it; out of range never blocks.** … · `NoteBar` *The rule — required or optional — is set once per reading on the template, at step 5 of 8. This screen shows what it produced.*
**Components:** Card · DataTable · StatusPill · Thumbnail · CountFooter · ConsequenceBox · NoteBar.
**Drawn on it:** `WM-49` (the rule, the file, and the two of them apart); rests on `WM-35` (flag, never refuse).

## Not in this file — twelve screens, pointers only

| Screen | Where it is today | Drawing |
|---|---|---|
| `Work-001` New connects · `Work-002` **the build** · Work orders · `Work-003` Work order drawer · `Work-004` New Connect wizard step 6 | `Work-001` is the *New connects* tab (`S86` reserved) · ⚠ **`Work-002` LANDS ON TWO HOSTS SINCE 2026-09-04 AND ON NO SCREEN OF ITS OWN** — see the stamp below · `Work-003` is a `?order=` drawer over either host's work-orders tab · `Work-004` is `S87` step 6 | blueprint §12, **not in this file**; the running screens are the reference |
| `Work-005` Work order templates (blank) · `Work-006` Work rail entry | exist — `S135` / `WRK-19`; the rail entry | blueprint §12; `Work-005` is replaced by `Work-013` |
| `Work-010` Phone · today · `Work-011` Phone · the job / safety gate · `Work-012` Phone · readings, parts, signature, close | new — the technician's phone | blueprint §14, **not in this file** |
| `Work-018` Settings › Reference data — Work group · `Work-019` Settings › Numbering — Work group · `Work-020` Assets — four disabled Work controls | exist — SET-04 cards · SET-08 · AST | blueprint §12.1; `Work-020`'s three checkboxes become the pre-tick that opens `Work-028` |

## ⚠ `Work-002` — STAMPED 2026-09-04 (`CR-070` wave O): its layout lands on TWO hosts

**PO, 2026-09-04:** *"youa re duplcaiting this - there is nothing called as
conenctions; Connection = Account only - you cannot have two differnt screen -
this is an integration problem"*, scoped the same day to *"One screen too many.
The objection is the duplicate destination — a person should reach the build's
progress, its units, its work orders and its charges from the account, not from
a parallel screen. Whatever the tables are called underneath, there is one place
to look."*

`Work-002`'s six regions no longer belong to one screen. **They split by what
owns the fact**, and four of the six were already drawn somewhere:

| `Work-002` region | Where it is now | Why there |
|---|---|---|
| Overview · the state, mode, target, charges, progress and unit count | the **premises**' new **Build** tab (`PRM-02`), and a **panel at the top of the account's Work tab** (`ACC-02`) | the premises is the host that ALWAYS exists because `connections.owner_account_id` is OPTIONAL — a build carries no owner account until one is asked for, and `BR-MET-116` refuses one on a build with no common area. Measured with `app.tenant_id` set 2026-09-12: **8 `brazosbend` connections, 0 with an owner account.** ⚠ **This cell blamed `create_owner_account()` raising `NotImplementedError("OQ-373")` until 2026-09-12 (`DEF-MET-5081`); `OQ-373` closed 2026-08-25 → `BR-MET-116` and the writer has existed since. The arrangement below is unchanged.** ⚠ On the account it is a PANEL and not a thirteenth tab: *Build* beside Bills and Payments would read as something the customer is billed for, and the question a person opens that tab with is *"what work is happening here"* — of which the build is the first half of the answer |
| The eight acts — *Hold… · Release… · Cancel… · Waiting on… · Add service · Mark outstanding work · Close · Raise order* | the same Build tab, `Cancel…` on the danger tier | they act on the build, so they belong wherever the build is read |
| Units | the premises' own **Units** tab, unchanged | a unit list is a fact about a PLACE, and drawing it twice is a second place for the same rows to be wrong (B14 rule 2) |
| Work orders | a **Work orders** tab on the premises and the **Work** tab on the account, each row saying which anchor it stands on | both are anchors and a person asks the question from either side |
| Assets | the premises' own **Assets** tab, unchanged | a meter list is a fact about a place |
| Charges · History | the account's **Bills**, **Adjustments** and **Audit** tabs, unchanged — **nothing new is built for either** | money and its trail are facts about a PAYER; a copy inside a Build tab would be the duplicate destination the ruling is about, one level down |

**And the screen id is retired.** `/:tenant/connections/:connectionId` still
resolves — every bookmark opens — but it is a DOORWAY that redirects, so it
carries no badge: `NCT-02` left `screenIds.ts` and
`10-scripts/gates/g29_allocated_badges.txt` in the same commit.

⚠ **THE DRAWING'S `TECHNICIAN` COLUMN IS NOT DRAWN AND IS NOT INVENTED.**
`work_orders` has no assignee column until wave `G`'s `metering/000N`
(`03-field-map.md` §3 rows 6–15), and a column that can never carry a value is
dead UI (law 2, `G13`). It is in the *where the drawing loses* table below.

## Where the drawing loses — every place, in one table

| Screen | The drawing shows | What is built instead | Because |
|---|---|---|---|
| `Work-031` | a taxes list filtered to field work | **nothing** | PO 2026-09-03 *"Dont add Tax on work order - for now"*; B4 §Tax is ❄️ frozen |
| `Work-032` | two tax lines and a $149.84 total; rates at 4 dp | cost ends at **$138.42**; rate *48.50* | the same ruling; hard rule 2 — display 2 on a customer-facing document |
| `Work-025` | ON HAND · REORDER AT · In cover / Below reorder · the Reorder box · *Issues deduct stock* | the register, the issue log, issue-against-a-job; **stock columns held** | `WM-22` *"stock levels are out of scope"* (`CR-028` D5); open question for the Work lane |
| `Work-023` | *She is blocked from 4 template types until renewed* | the watch and its dates, and the sentence **only where the tenant has switched blocking on** | `OQ-WRK-1493` RULED 2026-09-04 — *"(c) per-tenant, default warn"*. Both sides built; a default tenant does not render it |
| `Work-023` | a **TODAY** and a **UTILISATION** column | six columns; neither of those | `work_orders` has no assignee column until wave `G`, so neither can carry a value — dead UI (law 2, `G13`), the same call `Work-002`'s TECHNICIAN column got |
| `Work-024` | a *THIS MONTH* panel — *Jobs closed 88 · 92% · −4 min* — and four tabs | Overview and Certifications; **no figures panel, no Jobs tab, no Audit tab** | the same missing column, plus wave `M`'s trail reader. A tab onto a screen that does not exist is a control onto nothing (`WorkShell.tsx`'s own rule) |
| `Work-007` · `Work-013` (every list) | five NAMED chips standing on the toolbar with their current value in them — *Type · all · Status · all · Priority · all · Technician · all · Area · all*, and *Filter by service ▾* on `Work-013` | **B14 rule 12's toolbar**: `[Search…] [All \| chips ×] [+ Filter ▾]`. The same dimensions are declared — six on the dispatcher, one on the templates list — but a chip appears only once its filter is APPLIED, and it carries a ✕ | **B14 rule 12, and `DEF-442` is the PO's own instruction that put it there**: *"also look at Filter in Proto - it is panel and when you select somethibg it shows selection on screen ; look at filters you build"*. What we drew before that ruling was one labelled control per dimension, permanently on the toolbar — which is what these drawings draw. Building it back on the Work screens would re-open a closed defect on five screens and would grow a Work-only toolbar, which rule 36 forbids by name. **The drawing loses on the CONTROL and wins on the DIMENSIONS**, and all six are declared |
| `Work-007` · `Work-013` (every list) | no download control | **no download control** — CR-045 owns the one that is coming | ⚠ **THIS ROW SAID *one download glyph* UNTIL 2026-09-05 AND NOTHING RENDERED ONE (`DEF-WRK-4047`).** `DataTable`'s `downloadSlot` is passed by none of the six Work screens. The `Work-007` entry above had it right — *"no download glyph — CR-045 adds it"* — so one document contradicted itself two hundred lines apart, with the wrong half in the table a reader consults to settle exactly this. A *what is built instead* column written during a build easily records the wave's INTENT; it means what a person opening the screen right now will see |
| `Work-007` · `Work-013` · `Work-022` · `Work-023` · `Work-025` (five of the six) | a CAPS SECTION CAPTION inside the card above the table — *OPEN ORDERS · YOUR TEMPLATES · VERSIONS · TECHNICIANS · STOCK REGISTER · ISSUE LOG* | **no caption on any of them** | **DECIDED ONCE FOR THE MODULE, 2026-09-05, and the count is the argument: the product has 41 `DataTable` call sites and NOT ONE draws a section caption.** Adding five would make Work the only module that does, which is precisely what B14 rule 36 refuses — *compose the kit; where the kit lacks a piece, ADD IT TO THE KIT* — and adding it to the kit means a caption on 41 screens, which is a product-wide change nobody has asked for. It would also spend five new keys × eleven catalogues to print *OPEN ORDERS* above an H1 that already reads *Work orders*, which is rule 32's *a row never repeats what its own control offers* one level up. ⚠ **`Work-009` DRAWS NO CAPTION EITHER**, so the pack is not unanimous and the product already matches it on one of the six. If the caption is wanted it is a kit change and a B14 amendment, not five screen edits |
| `Work-007` | **SVC** as a single letter — `E`, `W` | the service's NAME — *Electric*, *Water* | a letter is a code, and the tenant names its own services (`BR-MET-109`), so `E` is not derivable for a utility that calls it something else — and the eleven services do not have eleven distinct initials (`Solar`/`Sewer`/`Storm water` all start with S). **The pack contradicts itself here**: `Work-009`, one screen along, spells SERVICE out in full. The product follows the spelled-out half |
| `Work-013` | **GATE** naming the gate and flagging it — *Meter set ⚑* | the pill **Gate** where the row IS the gate, and where it is not, **the utility's own stored reason** — *gated on the water service it derives from* | **THE TWO COUNT A TEMPLATE DIFFERENTLY.** The drawing draws one row per job SET (*New connection · Electric*, contents *2 tasks*), so its GATE cell names a step INSIDE the row. Here a template IS that step: seeded electric is *Service drop* and *Meter set*, two rows, and `is_gate` is on the second. Printing *Meter set* in the GATE cell would repeat the TEMPLATE column beside it (rule 32). The cell drew a bare DASH over the stored reason until `DEF-WRK-4048` |
| `Work-025` | the sentence *A system of record — what you own, where it sits, and who took it.* | *What your crews fit, and what each one costs.* | two of the drawing's three clauses describe things this screen does not have — *where it sits* is the LOCATION column and *who took it* is the ISSUE LOG, both held by `WM-22`'s *stock levels are out of scope*. A description promising two absent capabilities is worse than a shorter one (rule 32). **The sentence returns to the drawing's when the issue log lands in wave N** |
| `Work-025` | no UNIT column | a **UNIT** column between CATEGORY and UNIT COST | CLAUDE.md hard rule 3 — a quantity is always stated with its unit, never assumed. *78.40* is a price per something and the drawing never says per what. This is the one place on these six screens where the product ADDS a column the drawing omits |
| `Work-002` (the work-orders table, on both hosts) | a **TECHNICIAN** column | ORDER · SERVICE · STANDS ON · MODE · OUTCOME · STATE · the eye — **no TECHNICIAN** | `work_orders` has no assignee column until wave `G` (`03-field-map.md` §3 rows 6–15); a column that can never carry a value is dead UI (law 2, `G13`) |
| `Work-009` · `Work-014` · `Work-027` · `Work-028` | `accepted_by` · `WM-04` · `CR-028 D3` · `work_orders`/`connection_id`/`WM-01` in clerk-facing copy | the sentence without the id | B14 rule 32 |
| every drawing | a mono route bar with *signed in · M. Torres* | the staff shell's own top bar; the step counter in the wizard frame | the bar is the document's device, not a component |
| every drawing with a `WorkTabs` strip (`Work-007` · `009` · `013` · `023` · `025` · `026` · `027`) | a **BOXED folder tab** — border on three sides, page colour behind the active one — drawn **ABOVE** the page head | the shared page header's **UNDERLINED** strip, **BELOW** the title, accent-coloured, 14px, 8px×0 padding | B14 rule 36 (PO 2026-09-05, `DEF-WRK-3955`): the pack gives layout and detail, `r10` gives the visual style, the kit is how you comply — and rule 2, which gives a screen ONE page header and puts the strip inside it. Measured against Payments' strip in a browser by `10-scripts/render-checks/def-wrk-3955-work-tabs.mjs`; every property matches |
| `Work-007` · `009` · `013` · `025` (every module list) | the one sentence directly under the title, full width | the same sentence as the ACTIVE TAB'S EXPLAINER, below the strip, capped at **80%** of the column | B14 rule 18 (`--desc-measure`). The roll-up slot the sentence used to ride in sets no width at all, so every Work description ran the full width of the window |
| `Work-016` | the third reading, *New meter serial*, with a **dash in the UNIT column** | the same reading with the unit **`serial`** | `BR-WRK-015` makes the unit a COLUMN, CLAUDE.md hard rule 3 requires one, `wot_readings.unit_of_measure` is `NOT NULL` and `US-WRK-014` TC-3 (green since wave D) refuses a blank one BY NAME. Dropping the row instead would make the *Meter exchange* pack **2 readings** where this drawing, `US-WRK-016` §1 and `J60` step 7 all say three. CR-070 wave E, 2026-09-05 |
| `Work-014` | *START FROM A PACK* with four tiles and their counts | the same four tiles, with the counts **COUNTED from the pack's own rows** rather than typed | the typed constant said *Inspection · 3 tasks* where this drawing, §13.1 and `US-WRK-016` §1 all say **4**; a count written beside nothing to count cannot be contradicted (law 1). CR-070 wave E, 2026-09-05 |
| `Work-017` | **Delete**, a danger button, disabled with its note | **not rendered** | a DRAFT that has never been published has nothing to delete, and deleting a PUBLISHED template is `Work-022`'s control, which exists and carries the same refusal with its count (`BR-WRK-012`, `BR-SHL-025`). Two controls for one act is the second answer the 2026-09-05 ruling names. CR-070 wave E |
| `Work-022` | the versions history as a `DataTable` | the kit's `PlainTable` inside the tab's `Panel` | rule 20's ONE table type — a few rows of history inside a panel is what `PlainTable` is for (51 other sites), and it carries the 13.5px body / 12px uppercase header tiers the drawing's own table type implies. It was a hand-rolled `<table className="w-full text-left">` until 2026-09-05, with neither tier |
