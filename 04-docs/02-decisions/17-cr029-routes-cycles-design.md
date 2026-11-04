# B17 · CR-029 — Routes & Cycles: the design record

**Status:** ACTIVE (CR-029 opened by PO ruling *"G0 - Yes now"*, 2026-08-23)
**Authority:** the PO's rulings (CR-029 record, verbatim) outrank everything here.
Where this document and the upgraded prototype disagree with a ruling, **the ruling wins** — §3 lists every such place.
**Reference for these screens:** the **upgraded prototype (PO-updated 2026-08-23)**, which supersedes r10 for every Routes & Cycles surface exactly as r10 superseded r9. r10 remains the reference everywhere else.

---

## 1 · What a route and a cycle are

**A ROUTE — the field's grouping: who gets read together.** A named set of premises
(stored per unit underneath), created in Settings, **stamped onto each unit's service
points** — and that stamp is how every other module finds it. A meter is "on RT-001"
only because its service point carries that stamp. Walk/drive routes carry a reading
order; AMI routes group by feeder and read themselves.

**A CYCLE — the billing calendar's grouping: who gets billed together, and when.** A
**definition, not a schedule**: frequency + start day + days-to-complete, grouping
routes. A route belongs to exactly one cycle. The cycle's stamp rides the same service
points.

**Why they are required.** Without routes, 1,200 monthly reads are an unordered pile —
no walk order, no "route 3 is done", nothing a reader can carry. Without cycles every
account bills on one giant day — no staggered workload, no cash-flow spread, no due
date, no dashboard countdown. They are the two spines Reads and Billing hang from.

---

## 2 · The ruled model — grouping only, and three fields about time

PO, verbatim (pre-CR, recorded in the CR-029 record and the decision log):

> *"routes and cycles are grouping only - so we will not tag late fees , etc - we can
> capture start day, frequency, monthly, weekly daily, biweekly, once in two months ,
> quaterly etc and days to complete it ; give business names to frequence - 1 word."*

A cycle captures exactly three things about time:

| Field | Meaning |
|---|---|
| **Start day** | when the window opens (day-of-month for monthly-and-slower; weekday anchor for weekly/fortnightly; n/a for daily) |
| **Frequency** | one business word, from the vocabulary below |
| **Days to complete** | how long the window runs — **start day + N days IS the read window**, which retires the legacy from–to day pair |

**The reading window is DERIVED, never stored.** The upgraded prototype states it as
product copy: *"Derived, not stored"* (SET-07D.schedule) and *"The reading window is
derived from them — it is not something you set separately"* (SET-07.3).

### The frequency vocabulary — eight one-word business names

| Word | Means | The PO's phrasing |
|---|---|---|
| **Daily** | every day | "daily" |
| **Weekly** | every week | "weekly" |
| **Fortnightly** | every two weeks | "biweekly" — named Fortnightly because "biweekly" also means twice-a-week in common use |
| **Monthly** | every month | "monthly" |
| **Bimonthly** | every two months | "once in two months" |
| **Quarterly** | every three months | "quaterly" |
| **Semiannual** | every six months | the "etc" |
| **Annual** | every year | the "etc" |

**Money never touches these surfaces** (BR-MET-078, hardened by this CR). The one
boundary the PO drew explicitly at D9: **bill day and due days are DEFAULTS the cycle
carries and the run may override** — they are not "late fees, etc".

---

## 3 · ⚠ Where the rulings SUPERSEDE the upgraded prototype — READ BEFORE BUILDING A SCREEN

The screenshots are the reference; the PO's word outranks them. **SIX places the new
design must NOT be copied literally** — four ruled before the build, and **two ruled on
2026-08-23, after the screens were already built to the drawing** (D14, D15 below). A
lane that builds these has built the wrong thing even though it matched the screenshot.

| # | The screenshot shows | The ruling | What gets built |
|---|---|---|---|
| **D6** | Reader/device in wizard step 1, a Reader column on SET-05, and an inline reader edit on the SET-06D Facts rail | *"not required"* | **None of it.** Reader assignment is out of CR-029 scope; `routes.assigned_to` stays as it is, unwritten from the UI. The ops tab's existing read-only reader display is untouched. ⚠ **PARTLY SUPERSEDED 2026-10-24 (PO, MQ-033 — decision log of that date):** `routes.assigned_to` IS now written from the UI, on **Reads → cycle → Routes** only (Reader column, Assign/Reassign, bulk assign — `DEF-MET-10591`). The three Settings surfaces this row names stay reader-free. |
| **D9** | *"Bill and due dates belong to the run, not the cycle"* — on SET-07.3, SET-07.4 and the SET-07D Facts rail | *"when we configure Cycle we are provideing default values; mostly it wil remain as it is but user can over ride them during billing"* | **Bill day + due days STAY ON THE CYCLE as defaults, overridable at the run.** The copy changes to say defaults-overridable; billing's due-date math keeps reading the cycle and gains a per-run override. |
| **D12** | A Balance column ($142.30, $88.10…) on SET-06D.accounts | *"not required"* | **No Balance column.** The tab stays status-only — grouping-only wins. |
| **D13** | A per-row *"Assign a cycle →"* action on SET-07D.coverage | *"Cycles are not directlya ssing to accounts it is derived and determined at the time of bill run"* | **No account-level cycle assignment exists.** The cycle derives account → unit → route → cycle **at bill-run time**. Uncovered accounts are shown with what they actually lack (a route); the remedy is to route them. |
| **D14** ⚠ | The SET-06D.audit **Read history** with a **Reader** column — *"Aug 2026 · Aug 3 · **M. Chen** · 196 · 196 · Complete"*, *"May 2026 · **D. Ortiz** · 191/196 · 5 skipped"* — and the change-log line *"Reader changed · D. Ortiz → M. Chen"* | **OQ-343, CLOSED 2026-08-23:** *"B: no reader anywhere, correct the screenshot and drop the stored name"* | **Neither is built, and §4's column list below is WRONG where it says *Reader*.** The Read history is **Window · Read on · Collected · Expected · Result**. The change-log line is not rendered. **The stored name goes too:** `read_windows.reader` is dropped by migration and `RouteReadWindowRow` no longer types `reader_id`/`reader_name`. ⚠ **`routes.assigned_to` and the ops tab's read-only reader display are NOT touched** — D6 preserved them and the PO was not asked. |
| **D15** | r10's SET-04 *"Areas & sub-areas"* list, which duplicated the routes registry byte for byte (the upgraded prototype does not touch SET-04, so it neither fixed nor confirmed this) | **OQ-338, CLOSED 2026-08-23:** *"A: geography only - option a"* | **An area is a TAG ON A PREMISES; a route is created and edited in exactly ONE place, the routes registry (SET-05).** SET-04 holds areas and nothing route-shaped — no route column, no route count, no route editing. Written down as **BR-MET-103**. This is what the code already did, so it is a conformance-and-documentation ruling, not a rebuild. |

**Everything else in the upgraded prototype is the specification.** Where it disagrees
with r10 or with A1–A17, the upgraded prototype wins for these screens and the stale
document gets filed, not followed.

---

## 4 · The screens, with IDs

| Screen | ID | Today | Target |
|---|---|---|---|
| Settings · Routes & Cycles | `S8 · SET-05` | Built (CR-006), two stacked tables | Routes \| Cycles **sub-tabs**, each with its own toolbar and pager |
| Routes landing | `SET-05` (routes sub-tab) | Built | Route # (RT-001, links to detail) · Name · Type (AMI · AMR · Walk) · Service(s) · Area · Members · Meters · Cycle · Status; filters, column chooser, server-side pager. **No Reader column (D6)** |
| Cycles landing | `SET-05.cycles` | Built | Cycle # · Name · **Frequency · Start day · Days to complete** · Routes (chips) · Accounts · Status; the landing coverage sentence *"42 accounts sit on no cycle — they are never read and never billed until one is assigned"*; **no money column** |
| New/edit route wizard | `SET-06.1–4` | Built, unaddressable | Full-page, refresh-safe, own screen IDs. 1 Details (code suggested from series, editable · name · read type with explainer · **service SET** (D10) · area · notes — **no reader field**, D6) → 2 Select premises (search, area chips, "moves from RT-002" badges) → 3 Meters (expandable premises rows → unit/meter sub-table; exclusions unticked with a **two-word reason**) → 4 Review (*"No meter · verify · 3"*, **Save as draft / Activate route ✓**) |
| New/edit cycle wizard | `SET-07.1–4` | Built, unaddressable | 1 Details (code from series · name · Frequency; rail *"What a cycle does not hold — No late fees, no penalty dates, no amounts…"*) → 2 Select routes (**multi-select**; Current-cycle column; *"Picking a route that already has one moves it here"*; live tally) → 3 Schedule (the three fields + derived-window sentence + **Next three windows**; **bill/due day shown as cycle DEFAULTS**, D9) → 4 Review (counts, First run, coverage callout, *"Creation is audit-logged"*, **Save as draft / Activate cycle ✓**) |
| **Route detail** | `SET-06D` | **Does not exist** | Header + actions (Edit · Deactivate · Delete-with-reason) · Facts rail (Route # · Read type · **Service(s)** · Area · Premises·units · Meters on route (N excluded) · Cycle link — **no reader row**, D6) · five tabs: **Premises** (walking order, drag-to-reorder, **sequence per PREMISES** (D11), Print route sheet, "no meter · verify" rows) · **Units** · **Assets** (excluded rows explaining themselves in place) · **Accounts** (status only — **no Balance column**, D12) · **Audit** (Read history: Window · Read on · ~~Reader~~ · Collected · Expected · Result — **the Reader column is REMOVED by D14/OQ-343 and this row is left struck through rather than silently edited**; Change log, this route only, inline, and **without** the screenshot's *"Reader changed"* line). Hint where members render: *"Members derive from area tags — changes apply at the next read window."* |
| **Cycle detail** | `SET-07D` | **Does not exist** | Header + actions · Facts rail (Cycle # · Frequency · Start day · Days to complete · Routes · Accounts · Status; footnote *"Charges and taxes live on the plan, never here"* — amended for D9 so it does not deny the cycle's date defaults) · five tabs: **Schedule** (STARTS · DAYS TO COMPLETE · WINDOW *"Derived, not stored"* · FIRST RUN · Next three windows with statuses Next/Scheduled · FROM NEXT: *"Changing the schedule applies from the next window — nothing already issued changes"*) · **Routes** (*"Moving one here removes it from its old cycle at the next window"*) · **Coverage** (KPI trio + uncovered list — **no "Assign a cycle →"**, D13) · **Runs** (run history, Open in Billing →) · **Audit** (inline change log; System and Migration are first-class actors) |
| Reads · Routes / Cycles tabs | `S26 · RDS-02R` / `S27 · RDS-02C` | Built; S27 shows legacy columns | Adopt the new schedule vocabulary, cross-link to the details, own pagers |

---

## 5 · How it works today, and the gaps this CR closes

**Today, stage by stage:** (1) configure in Settings → (2) membership stamps service
points (drafts stamp nothing) → (3) reads collect with an **immutable** per-read route
stamp → (4) the bill run picks the cycle and scopes by the stamp, idempotency key
(tenant · cycle · period) → (5) dashboards derive live. **Stage 6 — generate the next
period — does not exist.**

| Gap | What is wrong | Closed by |
|---|---|---|
| **G1** | The calendar does not tick: frequency and day defaults are read by nothing; `read_schedules` has no writer and zero rows; every period is typed by hand into the run wizard | **D1** → RC-W2 |
| **G2** | Two generations of cycle columns; billing, the run picker and the ops tab still read the legacy calendar dates, so a cycle created today shows **no window** | **D2** → RC-W1 |
| **G3** | The ruled cascade (BR-MET-082 Am.1, run-time resolution) was never built: a stored answer patched by two cascade paths; a premises moved between areas keeps its old routes; accounts have no modelled path to a cycle | **D4** → RC-W4 |
| **G4** | The meter-attach path skips the draft check — a draft route's stamp can reach billing (likely bug, no ruling needed) | RC-W4-T3 |
| **G5** | `walk_order` exists with a uniqueness constraint and **no writer**; no screen shows it, no route sheet consumes it | **D3 + D11** → RC-W1/W3 |
| **G6** | Routes drive nothing operational (no route sheet, no dispatch) | RC-W3 (sheet); reader/dispatch **out of scope by D6** |
| **G7** | Unpaginated lists with per-row N+1; seeded routes carry no service/area; four open cosmetic defects | **D7** → RC-W3/W5 |
| **G8** | r10 disagreed with itself 13 ways | Settled by the upgraded prototype except the Areas registry → **OQ-338**, **CLOSED-RULED 2026-08-23** (*"A: geography only - option a"*) → **D15** above and **BR-MET-103**; closed in code by CR-029 RC-W6b |

### The dynamism audit — and how D4 collapses it

Events that today do **not** re-wire: a premises moved between areas (keeps old
routes) · a route whose area changes (members not re-derived) · a unit moved between
premises (no cascade found on that path) · an account opened/closed (no modelled link
at all) · a routed unit with no meter (no service point → invisible to the bill run).

**D4's answer:** scoping questions — *who is on this route right now? which units does
CY-001 bill? is anyone uncovered?* — are **derived live** from the current tags at the
moment Reads or Billing asks. Stored rows keep exactly two jobs: **explicit human
choices** (a hand-picked premises, an excluded meter, a walk order) and **immutable
history** (the route stamped on each collected read, which audits and delete-guards
depend on). Every stale case above then needs no cascade code, because nothing goes
stale. The upgraded prototype's SET-06D.audit change log — *"12 premises moved in from
RT-002 (re-districting)"*, *"MTR-W2262 excluded · premise demolished"* — assumes exactly
this, rendered as route-scoped inline audit rows.

---

## 6 · Schema consequences (all in RC-W1, migrated once)

| Change | Why | Ruling |
|---|---|---|
| `cycles.start_day`, `cycles.days_to_complete`, the eight-word frequency vocabulary; legacy calendar columns deprecated → dropped at W5 | one schedule generation | D2 + the pre-CR ruling |
| Bill day / due days **stay on `cycles`** as defaults; the **run** gains an override | D9's ruling, superseding the prototype copy | D9 |
| A route serves a **service set** (or service moves to membership) | RT-001 is "Water + Electric" | D10 |
| `route_meter_exclusions.reason` — two words, shown in place | SET-06D.assets renders reasons inline | design |
| Walk order at **per-premises** grain; first writer ever | one stop, many meters | D11 |
| **Read windows become first-class closable records** (window · reader · collected · expected · skips · result) replacing the writerless `read_schedules` | SET-06D.audit's Read history is the acceptance shape | D1 |

🔒 Migrations are a sensitive path: each carries `HUMAN-REVIEW-PENDING` and a row in
`12-governance/09-human-review-ledger.md`.

---

## 7 · The waves

Standing on every wave: **tests before code, every guard proven RED first,
pathspec-scoped commits, write-back as facts land, a version bump the screen shows.**

### RC-W0 · Seed & test data (2 tasks)
- **W0-T1** Seed routes and cycles to the full model: RT-001… / CY-001… grammar, routes **with service sets and areas** (closes the seeded-routes-are-empty defect), a walk route with real per-premises walk orders, a meter exclusion with its reason, cycles across frequencies. *Done when:* the demo tenant exercises the area filter, the cascade and every wizard field; zero routes with null service/area.
- **W0-T2** Dynamism + schedule fixtures: a scenario per dynamism-audit row, and frequency cases for all eight words including month-end edges (start day 31 · February). *Done when:* fixtures committed beside the tests that consume them.

### RC-W1 · Schema & one schedule vocabulary (4 tasks) — kills G2
- **W1-T1** 🔒 Migration: the three schedule fields + frequency vocabulary, old values mapped, backfilled from legacy columns, legacy marked deprecated.
- **W1-T2** Every reader moves to one generation (run picker, due-date math, ops Cycles tab, exports). *Done when:* a cycle created through the wizard shows its window in the run picker and on S27.
- **W1-T3** The wizard Schedule step becomes the ruled three fields + derived-window preview; **bill/due day presented as cycle defaults with a run override** (D9). *Done when:* no late/penalty control exists (asserted); already-issued figures provably unchanged.
- **W1-T4** 🔒 Route-side migration: service set (D10) · exclusion reason · **per-premises** walk order (D11) · read windows as first-class closable records. *Done when:* every SET-06D/SET-07D fact has a column behind it; no field invented beyond the screenshots.

### RC-W2 · The calendar ticks (5 tasks) — kills G1
- **W2-T1** The period engine: a pure derivation (start day + frequency + days-to-complete + first run) → the next N windows, computed on demand. Closing a window writes the W1-T4 record. *Done when:* all eight frequencies pass table-driven tests including month-end edges; a closed window renders the Read-history row (196 · 196 · Complete).
  ⚠ ~~**STUB AT OQ-339 — DO NOT CHOOSE A MONTH-END RULE.**~~ **CLOSED 2026-08-23 — RULED, and RC-W6 built it.** PO verbatim: *"there is no 31st feb so we have to manage either 28th or 29th of Feb."* — **CLAMP to the month's last day**, leap-aware because the PO named both February lengths. Monthly · start 31 · 3 days → February 2026 is **28 Feb – 2 Mar**; the same cycle in leap 2028 is **29 Feb – 2 Mar**. Skip and roll are rejected. **The clamp is PER OCCURRENCE and never moves the anchor** — March is back on the 31st. A start day of 29 in a **leap** February is a real date and is not clamped. The arithmetic lives ONCE, in `schedule.clamp_day_to_month`, called by both the generator and `derive_read_window`'s renderer, so the two agree **by rule** rather than by coincidence — which is what OQ-339 asked for in its closure. RC-W0's nine `UnruledEdge` markers are GONE from the fixtures: every case states its windows, and `UnruledEdge`/`UNRULED_CASES`/`open_questions()` were deleted rather than left empty (hard-won law 1).
  ⚠ **Weekly/Fortnightly:** no weekday-anchor column exists and `start_day` must NOT be overloaded (a 1–7 that sometimes means Monday is the ambiguity the one-word vocabulary was ruled to remove). If this wave needs the anchor, add a **new nullable column** for it; otherwise anchor on `first_run` as the fixtures do.
- **W2-T2** The run wizard **offers, never forces**: picking a cycle pre-fills the next period and the cycle's default bill/due dates, all editable (D9). Windows carry Next/Scheduled statuses; the FROM-NEXT rule holds.
- **W2-T3** *"Closes in 4 days"* counts to **the next cycle date** (D8②). **"Cycle completed" is NOT built** (D8①) — the dashboard stops claiming it.
- **W2-T4** A cycle-less one-time bill takes its due date **from the bulk-billing run** (D8③). The proration-denominator question is **withdrawn** (D8④) — no rule built; the OQ closes as withdrawn.
- **W2-T5** Tests-first engine + integration suite; RED-first proven on the engine's absence.

### RC-W3 · The screens (8 tasks) — built to the upgraded prototype

⚠ **EVERY SCREEN IN THIS WAVE IS TAILWIND — B14 rule 21, and the PO asked for it
explicitly (2026-08-23: *"Pls confirm UI is build using tailwind for Routes and
Cycles?"*, and on 2026-08-22 for the premises screens: *"all should be done using
tailwind"*).** Rule 21: *"A new screen, component or piece of UI is written in
Tailwind utilities and adds NO class to a stylesheet."* G31 enforces it — the
declared-class count is a **ceiling** that may fall and never rise.

**Where CR-029 starts from, measured at HEAD (2026-08-23):**

| File | State |
|---|---|
| `features/tenancy/RoutesCyclesWizards.tsx` (1,756 lines) | ✅ **Tailwind** — migrated under CR-018 Route B, listed in `styles/route-b-migrated.txt`; its 421-line bespoke stylesheet was deleted |
| `features/tenancy/SettingsRoutesCyclesTab.tsx` (645 lines) | ⚠ **Not migrated** — 10 bespoke classes from `SettingsPage.css` (`settings-table`, `settings-frame-head`, `settings-search`, `settings-lede`, `settings-empty*`, `cell-num`, …) |
| `features/metering/RoutesCyclesPage.tsx` (428 lines) | ⚠ **Not migrated** — 6 bespoke classes from `metering.css` (`met-page`, `met-panel-hint`, `met-qualifier`, `met-muted`, `met-progress`, `met-progress-fill`) |

**The binding instruction for this wave:** all NEW UI — both detail pages, the
sub-tab landings, every wizard change — is Tailwind utilities and adds **no** class
to any stylesheet. Where a task rewrites an existing region of the two un-migrated
files (the landings and the ops tab are both substantially rebuilt here), that region
**converts to utilities as it is touched** and the file's line is added to
`styles/route-b-migrated.txt` once it holds no bespoke class. A region left untouched
may keep its existing class — CSS shrinks, never grows. **No screen borrows another
feature's classes** (the `ImportAccountsWizard` mistake: a customers screen reaching
for metering's `met-*`).
- **W3-T0** Kit prerequisite: `DataTable` gains expandable rows (`renderExpanded` + Expand/Collapse + Expand all); B13 registry row updated. Needed by SET-06.3.
- **W3-T1** Routes landing to SET-05 as screenshotted + **server-side pagination and sorting** (D7). **No Reader column** (D6).
- **W3-T2** Cycles landing to SET-05.cycles as screenshotted (sub-tabs, three schedule columns, route chips, landing coverage sentence, no money column — asserted).
- **W3-T3** **Route detail (new screen)** to SET-06D: five tabs, drag-to-reorder **per-premises** walking order (walk_order's first writer), Print route sheet, exclusions with reasons, Read history + Change log inline. **No Balance column** (D12), **no reader rail row** (D6).
- **W3-T4** **Cycle detail (new screen)** to SET-07D: schedule card with derived windows and statuses, routes, coverage (**no "Assign a cycle →"**, D13), run history into Billing, inline audit.
- **W3-T5** Wizards become addressable full-page routes with screen IDs (refresh-safe); Edit opens **pre-filled** with "Save changes ✓".
- **W3-T6** Ops tabs adopt the vocabulary, cross-link to the details, get their own pagers.
- **W3-T7** Tests-first FE suites + the open cosmetic batch (plural forms, B14 sizes, wizard empty state).

### RC-W4 · Dynamism — resolution at run time (5 tasks) — kills G3, ruled by D4
- **W4-T1** Derived membership through the tags at the moment Reads or Billing asks; stored rows keep only human choices and immutable history.
- **W4-T2** The audit's scenarios as tests — each re-scopes correctly at next use; the two open high-severity defects close by construction.
- **W4-T3** The draft leak fixed (attach path), test first.
- **W4-T4** Meterless routed units become billable-visible.
- **W4-T5** **The account's cycle derives at bill-run time** (D13): account → unit → route → cycle; coverage reads live; no account-level assignment exists (asserted absent).
- **W4-T6** ⚠ **CLOSE THE MULTI-SERVICE MEMBERSHIP HOLE — handed over by RC-W1, deliberately not papered over there.** D10 gave a route a service SET, but `routes.service_id` was kept as a transitional head because `route_memberships.service` denormalizes from it and BR-MET-074's two partial unique indexes key on it. **The consequence, stated plainly: a "Water + Electric" route enforces per-service membership uniqueness for WATER ONLY — so the same unit can also join an electric route, and be read twice.** RC-W1 did not invent a constraint to close it, because the correct fix is to re-model membership against the service SET, which is exactly what D4's run-time resolution does. *Done when:* a unit on a multi-service route cannot also join another route for any service in that set; the uniqueness guarantee is proven for **every** service in the set, not just the head; and `routes.service_id`'s transitional role either ends here or its remaining readers are named.

### RC-W5 · Naming, docs & close audit (4 tasks)
- **W5-T1** The `RT-001`/`CY-001` grammar end to end (D5), counts reconciled to one truth. ~~⚠ **Stubs at OQ-338** (the Areas-registry half was not ruled).~~ **STUB REMOVED, RC-W6b 2026-08-23** — OQ-338 is CLOSED-RULED (*"A: geography only - option a"*) and `tests/test_cr029_rcw5_naming.py` now asserts the ownership it makes law: no reference list is a second routes registry, an area row publishes nothing route-shaped, and `/lookups/areas` REFUSES a route-shaped field rather than ignoring it.
- **W5-T2** Legacy cycle columns dropped; the per-row derivations batched (no N+1) (D7).
- **W5-T3** Docs write-back: the epic re-reconciled, the API audit's missing endpoint rows, the rule amendments, this document kept current.
- **W5-T4** Close audit: full gates + suites, impact sweep, every debt item fixed or ruled out, version bump, consolidated sign-off.
- **W5-T5** ⚠ **RE-POINT FIVE BACKEND MESSAGE KEYS at the sentences RC-W3c wrote.** Each currently reuses a borrowed key as a deliberate stopgap (a zero-baseline gate blocks unkeyed refusals and the catalogues belonged to another lane at the time); the proper sentences now exist in all 11 catalogues, and **until this lands G18's dead-key count sits 5 higher (34 → 39) — exactly these five and nothing else**. (a) `apps/billing/api.py::_optional_due_days`, both `message_key` and `field_errors[0]`: `metering.cycle.due_days_range` → **`billing.run.due_days_invalid`**. (b) `apps/metering/read_windows.py` (~lines 170 and 176, both): `metering.premises.status_unknown` → **`metering.readWindow.result_unknown`** (same `{{allowed}}` param). (c) `apps/metering/walk_order.py::_REFUSAL_KEY`, split per call site: 179 → **`metering.route.walk_order_duplicate_premises`**, 183 → **`…_duplicate_position`**, 187 → **`…_not_a_member`**, 193 → **`…_incomplete`**; the three shape refusals (156/164/167/174) keep `metering.payload_not_object`, because *"We couldn't read that change"* is the right sentence for a malformed body. None of the four takes an interpolation, so `_refuse` needs no `params` change.
- **W5-T6** **Migrate the eight list callers to the paged envelope.** RC-W3b made `/routes` and `/cycles` paginate **only when `?page=`/`?per=` is sent**, because unconditional would have broken eight shipped callers that read these lists as bare arrays and call `.filter`/`.find`: CycleDetailPage (row + Routes tab), RoutesCyclesWizardPages, RoutesCyclesPage, ReadsListPage, UploadReadsWizard and BillRunWizard's cycle picker. Both branches are tested today. Migrate the callers, then retire the bare-array branch. Note `GET /billing/runs` and `GET /routes/{id}/read-windows` use the bounded-history posture (`limit`, no `page`) deliberately — they may join the paged grammar here or stay, but say which.
- **W5-T8** ⚠ **A BROWSER WALKTHROUGH — hard-won law 6, and it has not happened for ANY CR-029 screen.** Every gate in this repo stays green over a screen that renders nothing; nine defects were once found by diffing the running app against the prototype and by nothing else. Walk SET-05 (both sub-tabs), both wizards, SET-06D's five tabs and SET-07D's five tabs against the PO's upgraded screenshots, click the drag-to-reorder and confirm its save persists, and record what is found. RC-W3c stated this absence in both screen trailers rather than let it pass silently.

**Order:** W0 and W1 start together (W0's new-field seeding lands after W1-T1); W2 and
W3 then run as two parallel lanes (backend-pure vs frontend-heavy, meeting at W3-T4's
windows card); W4 needs W2's engine and W0's fixtures; W5 closes.

---

### RC-W5 · WHAT ACTUALLY LANDED, 2026-08-23 (written by the W5 lane, at close)

**Product version 2.40.2.** Golden **33 PASS / 0 FAIL** before and after — no ❄️ FROZEN
B4/B5 figure moved in any wave of this CR.

| Task | Landed | What is worth knowing |
|---|---|---|
| **T1** naming | ✅ | The second grammar was still being MINTED. `apps/metering/sample_data.py` — the BR-TEN-056 sample plant that runs for **every** tenant taking sample data, not just the demo — created `SCW-M` / `SCW-R1` and wrote three deprecated columns. It allocates from the `CY-`/`RT-` series now, carries the three ruled schedule fields and a real service set, and keys idempotency on the sample rows' NAMES (a series code differs on every call). ⚠ **Adoption path: FRESH TENANTS ONLY.** A tenant already holding `SCW-*` keeps it — recognised as seeded, never duplicated, never renamed. Renaming a shipped route or cycle code is a data migration with its own blast radius (a code appears in exports a utility has already filed) and nothing rules it; **reported**. |
| **T2** legacy columns | ✅ **6 of 6** | `window_start` · `window_end` · `read_day_from` · `read_day_to` · `due_day` dropped (metering 0021, 🔒 HUMAN-REVIEW-PENDING). ~~**`bill_date` STAYS**~~ — it was the sixth, held back because `apps/billing/issue.py::_due_terms_for` read it as the fallback bill date and **no ruling said what replaced it**; the three candidate readings sat up to a month apart, each producing a different due date and therefore a different late-fee start (BR-BIL-001), so W5 reported OQ-344 rather than answering at a call site. **OQ-344 CLOSED 2026-08-23** (PO: *"I'd say B - these are defualt - user can override"*) and **RC-W6's metering 0023 took it** — the fallback is now *"the bill day, in the month AFTER the period ends"*, derived. |
| **T3** docs | ✅ | This section · the epic's re-reconciliation box · the API audit's six missing rows · A11's `due_days` row · BR-MET-009/077/078 and BR-REP-027 amended. |
| **T5** message keys | ✅ | G18 dead-key count **39 → 34**, exactly the five B17 named. |
| **T6** paged envelope | ✅ | Eight callers migrated; both bare-array branches retired. **`GET /billing/runs` and `GET /routes/{id}/read-windows` STAY on `limit`, no `page`** — a history grows at the TOP, so page 2 of it serves duplicates and skips, and neither tab has a pager to drive one. |
| **T8** walkthrough | ✅ | **It happened, in Chromium, twice.** The drag-to-reorder **persists across a reload** — the one feature whose writer landed last and had never been exercised by a human. It also found the two defects below. |
| **T4** close audit | ✅ | Full gate run + suites; the impact sweep across billing runs, reads, dashboards and reports. |

**⚠ THE TWO DEFECTS THE WALKTHROUGH FOUND, AND NOTHING ELSE DID.**

1. **The SET-05 Cycles sub-tab lost six of its nine columns** for anyone who landed on
   Routes first and clicked across — which is everyone. Both sub-tabs put a `DataTable`
   at the same position under the same parent, so React kept ONE component and its
   column-visibility state; the cycles table then dropped every key it does not declare
   and rendered the INTERSECTION: *Cycle # · Name · Actions*. Fixed with a distinct
   `key`. Every gate was green over it, because each suite renders one sub-tab.
2. **W5-T1's own fix broke the demo seed**, and the same walkthrough caught it. Once the
   sample plant allocated `CY-001`/`RT-001`, `seed_demo`'s code-keyed skip silently
   DROPPED the colliding definitions — the demo tenant lost *"Residential monthly"* and
   *"Katy North"*, six cycles became five — and the next fresh seed died on
   `metering.route.code_duplicate`. Idempotency moved to the NAME.

**⚠ A W1-T3 GAP FOUND BY W5-T2, worth recording because four waves passed over it.**
The shipped SET-07 cycle wizard still wrote `read_day_from` / `read_day_to` / `due_day`
and offered CR-006's **three** lowercase frequencies. The server had accepted only the
eight business words since RC-W1, the landing and the detail rendered them, and the
CREATE screen offered three — so a utility that bills weekly could not say so, and
nothing reported it. The step is rebuilt (Start day · Days to complete · Bill day ·
Due days, eight words, a derived-window preview). **The columns could not be dropped
until it was.**

**⚠ WHAT THE COLUMN DROP COST, stated rather than glossed.** BR-REP-027's cycle-status
line had FOUR states and has **two plus `not configured`**: `closed — bill run pending`
was derived entirely from the dropped day-of-month defaults, and a cycle with no
first-run date is now SKIPPED rather than counted down to. BR-MET-009's window-ordering
clause has no fields left to order. Both amendments are written into the rule files and
**reported for ratification** — no ruling named either loss explicitly.

---

### RC-W6b · WHAT THE FRONTEND OWED THE 2026-08-23 RULINGS (written by the W6b lane)

The seven rulings landed AFTER these screens were built. Four of them changed
something a screen already drew, and this is where each went.

| Ruling | What the frontend owed it | Where it landed |
|---|---|---|
| **OQ-343** *"no reader anywhere, correct the screenshot and drop the stored name"* | The Read-history Reader column and the *"Reader changed · D. Ortiz → M. Chen"* change-log line — **the PO's own screenshot corrected, not followed** — and the stored name out of the contract | §3 **D14** · `RouteReadWindowRow` no longer types `reader_id`/`reader_name` · `RouteDetailPage`'s trailer records the divergence · `RoutesCyclesRulings.test.tsx` scans every file under `src/` for a reader field being declared, read or indexed. ⚠ **The BACKEND column drop (`read_windows.reader`, a cross-module FK to identity) is `apps/metering/**` and is REPORTED, not taken** — until it lands the payload may still carry `reader_name` and no screen reads it |
| **OQ-338** *"geography only - option a"* | An audit of SET-04, and the ownership written down | §3 **D15** · **BR-MET-103** · three conformance tests in `test_cr029_rcw5_naming.py` (the W5-T1 stub is gone) · **the two places that DID claim otherwise are fixed**: `settings.reference.sample.areas` read *"Districts and ROUTES premises are grouped by"* under the card's own title, in all eleven catalogues, and `AreaLookupHandler`'s docstring opened the same way. The screen's behaviour was already the ruling |
| **OQ-340** *"first window 15–17 Sep (start day becomes decorative)"* | **Show what the cycle DOES.** The engine anchors on the first run and does not rewrite `cycles.start_day`, so five surfaces were printing a number the product ignores | The cycles landing's Start-day column and its read-window label, SET-07D's Facts rail · STARTS fact · WINDOW fact, the deactivate confirmation's quoted window, and a note in the wizard's schedule step. All read the SERVED `effective_start_day`; **nothing computes a day in the client**. The saved number is NAMED as unused rather than silently swapped — hiding the swap would hide that the operator's own field is being ignored |
| **OQ-341** *"you give warning and if user override; let them do it"* | Somewhere for the warning to appear. `schedule_warning` was served and **no screen rendered it** — "built is not wired" for a ruling rather than a component | SET-07D's Schedule tab, as a translated sentence keyed on the CODE (its `detail` is English prose from a Python module), **beside** the real overlapping windows |

**What this lane did NOT touch, deliberately:** `routes.assigned_to` and the ops
tab's read-only reader display (D6 preserved them and the PO was not asked), and
the OQ-339/341/342 engine stubs, which belong to the lanes that own them.

---

### RC-W6 · WHAT THE BACKEND OWED THE SAME RULINGS (written by the W6 lane)

Five of the seven land in `apps/metering/**` and `apps/billing/**`. **Every stub
this CR raised is gone; the engine now answers for every cycle a human can save.**

| Ruling | What the backend owed it | Where it landed |
|---|---|---|
| **OQ-339** *"there is no 31st feb so we have to manage either 28th or 29th of Feb."* | The month-end clamp, leap-aware, **per occurrence** — and ONE copy of it, since `derive_read_window` already clamped for rendering | `schedule.clamp_day_to_month` (the shared helper) · `period_engine._shift_months`'s `UnruledSchedule` raise deleted · the fixtures' nine `UnruledEdge` markers replaced by real windows, and the marker machinery deleted with them |
| **OQ-340** *"first window 15–17 Sep (start day becomes decorative)"* | The first run as the anchor — **and an honest answer to the field it makes decorative.** A stored `start_day` the engine ignores lies to the operator | `period_engine._anchor_day` (the stub is gone; `start_day` is not read at all once they differ) · **`period_engine.effective_start_day()`**, served on every cycle payload as `effective_start_day` + `start_day_differs`. ⚠ **The stored column is NOT rewritten** — it is the operator's own value and changing it silently would be a second, unruled decision |
| **OQ-341** *"you give warning and if user override; let them do it"* | Generation of the overlapping windows (the option was AMENDED from a refusal inside the ruling), plus a warning that NAMES the collision | `period_engine._walk`'s refusal deleted · `overlap_ceiling()` derives all eight words from the shortest gap the calendar can put between two occurrences (Monthly = **28** = February, the number the PO quoted) · `overlap_warning()` on `create_cycle`/`update_cycle`'s warnings AND on every cycle read as `schedule_warning` |
| **OQ-342** *"a real series (RUN-0001, like RT-001)"* | A real number series, allocated forward-only at run creation | `core.numbering.BILL_RUN` (the 23rd series, default `RUN-{0000}`) · `bill_runs.run_no` + a PARTIAL unique index (billing 0023, 🔒) · allocation inside `create_run`'s own `atomic()` · the RC-W4b test that HELD `run_no` null is **inverted**. ⚠ `import_run`'s catalogue default moves to `IMP-{YY}{MM}{DD}-{00}` so two seeded series do not share the `RUN-` prefix; no stored row moves |
| **OQ-343** *"no reader anywhere, correct the screenshot and drop the stored name"* | The stored FK, the payload keys and the parameter | metering 0022 drops `read_windows.reader` (🔒) · `window_dict` serves neither key · `close_read_window` no longer ACCEPTS a reader (removed, not ignored) · the `select_related` goes with it. ⚠ **`routes.assigned_to` untouched**, asserted in two tests so a later lane cannot read this as licence |
| **OQ-344** *"I'd say B - these are defualt - user can override"* | The fallback bill date, and the last legacy column | `runs.default_bill_date()` — *"the bill day, in the month AFTER the period ends"*, clamped by OQ-339's rule · `effective_bill_date` takes a DAY and a period end · `issue._due_terms_for` and `selectors.cycle_terms_for` read `cycle__bill_day` · **metering 0023 drops `cycles.bill_date`** (🔒) · `cycle_dict` DERIVES the contracted `bill_date`/`due_date` keys from the cycle's next period rather than serving permanent nulls |

**THE COST OQ-341's RULING CREATES, AND IT IS UNPAID BY DESIGN.** With overlap
lawful, a read collected while two windows are open belongs to ONE of them and
**nothing says which**: `meter_reads` carries period dates and an immutable route
stamp and has **no link to `read_windows` at all**. Three readings (earliest open
window · latest open window · the crew names it, which needs a column) put the
read in different counts and therefore close a window at *196 of 196* or *195 of
196*. `read_windows.window_for_read` resolves the unambiguous case and **refuses**
the ambiguous one under a placeholder id, **REPORTED for minting** — the prime
directive, applied to a question this CR's own ruling created.

**Three 🔒 migrations carry `HUMAN-REVIEW-PENDING` and their ledger rows are
OWED and REPORTED** (this lane does not write governance files): billing 0023
(`bill_runs.run_no`), metering 0022 (drop `read_windows.reader`), metering 0023
(drop `cycles.bill_date`).

---

## 8 · Recorded, not asked — demo-data facts from the screenshots

1. SET-07.4 names the cycle *"Quarterly — irrigation"* beside Frequency = Monthly. Name is free text; **no coupling between name and frequency exists or gets built**.
2. Coverage arithmetic seam: 1,124 + 123 = 1,247 = the tenant's total connections, leaving no room for the 42 uncovered accounts. A seed artefact — the real build **asserts coverage math by test**.
3. SET-07.2's route selectors render radio-style but must be **multi-select** (CY-001 holds three routes).
4. No edit-mode screenshot exists in the set; "Save changes ✓" is asserted from the instruction and verified at build.
