# CR-092 lane 6 · Standards, journeys, absences and what crosses a boundary — STEP 1, identify only

**Read on** 2026-09-11 · **branch** `claude/hi-0jmv62` · **tip** `0a1a677d9` · **version** `2.237.0`
**Source document:** the Assets-menu blueprint (artifact `2f979496`), sections 01, 07, 08, 09, 10, 11 and 13.
**Scope:** everything in that document that is *not one screen*. Five sibling lanes have the screens.

**This lane changed no component, catalogue, route, stylesheet, gate, test, rule, epic, question or
story.** It read code, ran gates, measured what could be measured without a browser, wrote this file,
and filed defect rows. Section 9 lists every row filed and — more usefully — every finding that is
**already filed and open**, so step 2 does not file it a third time.

---

## 0 · The single most useful paragraph for the other five lanes

The blueprint has been revised 48 times. **Five findings it made and then withdrew, four specification
numbers it struck, and five assumptions it corrected are still visible in the source files that
produced them.** A lane reading those files fresh will re-derive them and file them as new. Section 6
below is that list. **Read it before filing anything.** The one most likely to recur: the Map tab's
four raw `<select>` elements — still four raw `<select>`s on this tip, still with no `appearance` in
their own class — which are **not** a rule-8 violation, because `FormModal.css:411,423` gives
`.view select { appearance: none }` and the browser confirmed the chevron is drawn.

---

## 1 · The twelve rule rows, judged against B14, with the *Enforced?* column filled in from the gates

The blueprint's section 09 carries **12 data rows** (counted in its own table) plus one `NFR-3` callout.
Its closing sentence says *"four of the eleven above"* — the table has twelve. Both facts are below.

**The authority is B14** (`04-docs/02-decisions/14-ui-conventions.md`), read in full rather than as a
summary. **The *Enforced?* column below was derived by reading the gate that would have to catch each
one**, not copied from the blueprint.

| # | Rule | Verdict on this tip | Whose defect | **Enforced? — the gate actually inspected** |
|---|---|---|---|---|
| 1 | `BR-WRK-056` — the Assets door has four ways in | **Breached.** `raiseWorkOrderPath` appears in five asset files and **0 times in `AssetDetailPage.tsx`**. The rule is CONFIRMED and reads *"the action bar, the Maintenance history panel … all post it"* | assets | **No.** Nothing asserts a control's *absence*. `G100` does ask *has anything started pointing at this screen* — but it walks the **customer-portal register only**, so it could never have seen this |
| 2 | B14 rule 39 (the blueprint calls it R12) — label → input → helper | **Breached on 10 of 18 fields** (the blueprint's browser measurement; not re-measurable here) | assets | **No.** Rule 39's own status column says *"NO GATE READS COMPUTED SPACING"*. `07-frontend/src/portal/components/spacingAnchors.test.ts` asserts token *names*, in the portal only |
| 3 | B14 rule 18 + the six-to-eight-word convention | **Partly. Four of six over budget; two render nothing — and those two are a PO RULING, not a defect** (see §7.1) | assets | **No** for the word count. `G43` clause (b) is a ratchet on `max-w-prose` at 50 — a *width* check. Nothing counts words in a description, and nothing asks whether a declared slot is filled |
| 4 | B14 12 · 13 · 14 · 16 on the Lifecycle tab's three tables | **Breached.** They are the detail-panel table, not `DataTable`, so they inherit nothing | assets | **No.** `G43` clause (a) fires only on a list that *declares* `searchFields`; a hand-built table declares nothing and is invisible to it by construction |
| 5 | B14 rule 15 — max 2 visible + `…` overflow | **Breached, and product-wide** (§2.4) | **product-wide** | **Partly.** `G37` checks icons, the accessible name and single icon ownership. It does **not** count actions. Already filed: `DEF-2453`, open |
| 6 | B14 rule 7 — date input with a Today shortcut | **Breached.** No `Today` control exists in `FormModal.tsx` at all | assets (shared field kit) | **No.** B14's enforcement column for rule 7 is empty and no gate names it |
| 7 | B14 rule 31 — no database id is ever the visible value of a field | **Breached in a form none of rule 31's enforcers can see:** the screen *asks a clerk to type a uuid* (`AssetFlowPages.tsx:604-612`, help `assets.maintenance.techNoList`) | assets | **No, and precisely why matters.** `G28` reads strings; `G69` refuses a *truncated or joined* id in a cell; the two rendered-output checks cover `S30` and `S15` alone. A field whose **input** takes a uuid is outside all four |
| 8 | B14 rule 13 — click cycles asc → desc → **clear** | **Breached in the shared table.** `DataTable.tsx:53-59` `nextSortState` toggles asc↔desc and never clears | **product-wide** | **No.** No gate in this repository names rule 13 (grepped all 123) |
| 9 | B14 rule 16 — `⇤ ← Page x of y → ⇥` | **Breached in BOTH shared footers, and worse than the blueprint says** (§2.2) | **product-wide** | **No.** No gate names rule 16. Already filed twice: `DEF-449`, `DEF-2449`, both open |
| 10 | `BR-SHL-025` — a role without write sees the control **disabled with its reason** | **Breached.** `writeBlockedReason` is declared on both tabs, passed by the page, and **read nowhere** | assets | **No — and this is a shape `G13` cannot see.** Census in §3 |
| 11 | R11 title size — one size per class of screen | **Two sizes, not split by kind** (the blueprint's browser measurement). The source half is verifiable and is itself wrong (§2.3) | **product-wide** | **No.** `G34` refuses arbitrary type values (`text-[13px]`); both 40px and 32px are legal tokens, and nothing compares a screen's *kind* to the token it picked |
| 12 | R11 spacing scale — 4 · 8 · 12 · 16 · 20 · 24 · 32 | **Three off-scale values, not two** — the blueprint names the rail item and the status pill and counts the KPI gap as conforming; it is `6px` where rule 39's anchor was amended to **8** hours before the blueprint was written (§7.2) | **product-wide** | **No.** The CR-016 browser check measures type sizes, control heights, native selects and kickers — **nine properties, none of them padding or gap** (`07-frontend/e2e/ui-conformance-baseline.json`) |
| — | `NFR-3` — universal server pagination | **Breached** (§4) | assets | **No.** Grepped all 123 gates: the string `NFR-3` appears in **no gate**. `G114` polices the *shape of the envelope declaration* in the front end, never whether a `LIMIT` reaches SQL |

### The total, said plainly

**Of the thirteen findings above, a machine would have caught none.** Five gates touch the *neighbourhood*
of one of them (`G43`, `G37`, `G28`, `G69`, `G114`) and each stops one step short of the thing that is
actually wrong — which is B14's own standing sentence, *"no gate in this repo reads rendered output"*,
measured rather than repeated.

### And the gates that DO enforce something were measured, not assumed

`python3 10-scripts/gates/run_gates.py` on this tip, before this lane wrote anything:
**77 PASS · 43 FAIL · 3 SKIP — MERGE BLOCKED**, and its own comparison line reads *"NO PREVIOUS RUN IS
RECORDED … Nothing is being compared. This is NOT '0 newly failing'."*

Two of those failures are this lane's subject:

* **`G37`, the one gate that enforces any part of B14 rule 15, is RED** — two findings:
  `components/Sparkline.tsx` declares an inline `<svg>` and `features/runbooks/home/RunbooksHome.tsx:476`
  puts a `<ButtonLink>` inside `<RowActions>`. **Dated rather than assumed** (`git log -S`): both arrived
  on **2026-09-06**, in `CR-075` waves C and D. **So rule 15 has been read as ENFORCED for five days while
  its gate was failing** — which is hard-won law 7's first shape, a guard nobody reads, sitting inside a
  suite with 42 other reds for it to hide in.
* **`G38`, the only gate that touches stated absences, is red for the ratchet reason**: *"75 stated
  absence(s); 11 cite a DEF or OQ, 64 cite nothing (baseline 65). DOWN from 65 — lower
  UNTRACKED_BASELINE to 64 to hold the gain."* A count that fell and was not banked is red on purpose
  (`DEF-077`).

**Neither is this lane's doing and both were red before it started.** Saying so *with the command that
proves it* is the habit `CLAUDE.md` asks for, after two lanes called the same red pre-existing in good
faith and one of them had caused it.

⚠ **AND THERE IS A SECOND LAYER NOBODY SHOULD ASSUME AWAY: NOTHING RUNS AUTOMATICALLY AT ALL.** All
seven workflow files in `.github/workflows/` end in `.yml.disabled` by PO ruling of 2026-09-04
(*"I have exhausted all my github actions free minutes"*). So even the gates that *do* enforce a rule
only fire when a person runs them. *Enforced* in the table above means *a gate would fail if somebody
ran it*.

---

## 2 · The rows that are product-wide, and what is already on the register

**This is the section that decides whether step 2 fixes a shared component once or six times.**

### 2.1 · Rule 13 · the sort cycle — NOT previously filed → filed here
`nextSortState` toggles forever. `DataTable` is mounted by **54 non-test files**, so this is every list
in the product, not an assets defect.

⚠ **It was found on 2026-08-18 and recorded where nobody would read it.** `DEF-211`'s closure text
names it exactly — *"rule 13's THIRD click (nextSortState toggles asc/desc and never clears)"* — as one
of *"THREE REMAINDERS, ALL IN THE SHARED COMPONENT AND ALL NAMED"*, and `DEF-211` was then **closed**.
A remainder written into a closed row is invisible: `defect_report.py` counts open rows. That is
hard-won law 7's first shape — proved once, never read again — applied to the register itself.

### 2.2 · Rule 16 · the pager — ALREADY FILED TWICE, BOTH OPEN → **do not file a third**
* `DEF-449` (2026-08-21, platform-shell, **open**) — no first/last, no *"Page N of M"*, no *"Showing"*.
* `DEF-2449` (2026-08-30, platform-shell, **open**) — the same three, measured in Chromium on the bills
  list, with the blast radius stated: *"DataTable is shared by 27 lists"*.

**And the blueprint's row understates it in two ways, both verified here:**
1. **There are two shared footers, and the fix reached one of them.** `ListPager.tsx` gained *"Page x of
   y"* on 2026-09-05 (`DEF-CWP-3977`) — nine consumers. `DataTable`'s own footer (`:934-975`, 54
   consumers) still renders range · rows-per-page · `‹` · `›` and **no page indicator**, although
   `table.pager.pageOf` exists in **all eleven catalogues**. One rule, two implementations, one fixed.
2. **No first/last control exists anywhere in the product.** The glyphs `⇤`/`⇥` appear in exactly
   **4 places in `07-frontend/src`, every one of them a comment quoting the rule.**

### 2.3 · R11 · the title size — NOT previously filed → filed here
The blueprint measured 32px on registry, detail, both wizards and reassign, and **40px on Raise work
order**. I cannot re-measure (§10). **The source half I can settle, and it is wrong on its own terms:**

* `tokens.css:203` — `--text-h2: 32px; /* page-head title — THE APP DEFAULT, every screen head */`
* `tokens.css:202` — `--text-h1: 40px; /* full-page wizard title */`
* `PageHeader.tsx:272` renders **`<h1>` unless `titleAs="h2"` is passed**, and `global.css:58` sizes a
  bare `h1` at `--text-h1` = 40px.
* **`titleAs="h2"` appears once in non-test source** (`features/notifications/TemplateDetail.tsx:601`)
  across **137 files that mount `PageHeader`**.

So the token sheet's *"THE APP DEFAULT, every screen head"* describes a default the component does not
have. One of the two is false whichever way the browser measures, which makes this hard-won law 1 —
a comment claiming a guarantee is not the guarantee — in the type scale.

### 2.4 · Rule 15's cap · counted product-wide
Measured over `07-frontend/src` (non-test): **63 `<RowActions>` blocks; 14 of them declare more than two
actions with no `…` overflow, in 14 files.** The assets registry's six (`AssetRegistryPage.tsx:663-724`)
is the largest; `SettingsReferenceData`, `PremisesListPage`, `PlansTab` and `RefundsPage` declare four.

`DEF-2453` (open) already carries this rule — **and it is now partly stale in a way worth knowing**: it
says *"no such component exists"*, and `RowActionsMore` **does** exist today
(`components/RowActions.tsx:237`) and is used by exactly one screen (`UnitsListPage.tsx:751`). What is
still true is its other half: **nothing counts the actions a cell offers.**

### 2.5 · The KPI gap — 6 where 8 is ratified → filed here
`components/KPIStrip.css:18` sets `gap: 6px`. B14 rule 39's anchor read *"KPI 16/20 gap 6"* when it was
ratified on 2026-09-11 and was **amended the same day**, on the PO's words: *"One off-scale value invites
the next one. 8 is the nearest step and nobody will see 2px."* The strip's side padding is right
(`padding: var(--space-4) 20px` = 16/20). Its twin on the portal is `DEF-CWP-4903`, open, filed today —
whose own text quotes the **pre-amendment** anchor, which is the same staleness one document further on.

---

## 3 · `BR-SHL-025`, and the shape `G13` cannot see — the whole-product census

**The rule, verbatim** (`04-docs/05-modules/00-platform-shell/02-business-rules.md`, CONFIRMED):
*"Action gating: forbidden actions on visible screens render disabled-with-reason (A18 §6 voice,
focusable); gating driven by server-provided permission set only; server independently enforces every
mutating call (403, no write)."* **So this is a UI-honesty defect, not a security hole** — the server
still refuses.

**What is wired and what is read, on this tip:**

| file | `writeBlockedReason` | what the tab renders for a read-only role |
|---|---|---|
| `AssetInventoryTab.tsx:74` | declared · passed by `AssetRegistryPage.tsx:911` · **read nowhere** | **Parts in Work →** (`:219`), ungated |
| `AssetLifecycleTab.tsx:93` | declared · passed by `AssetRegistryPage.tsx:920` · **read nowhere** | the raise-work-order row action (`:183-189`) and **Work rules →** (`:354`), ungated |
| `AssetImportsTab.tsx:97` | declared · passed · **read four times** (`:348`, `:353`, `:358`, `:386`) | the counter-example: the third tab on the same page does it correctly |

**Why no check sees it.** `G13` (`check_unwired_props.py`) asks, for every prop *consumed through an
optionality idiom*, whether a JSX caller supplies it. Here the caller supplies it. **Nothing asks
whether the component reads it** — and a prop consumed through **no** idiom is outside `G13`'s subject
by construction.

### The census, because two instances and a pattern are different things

Scanned every non-test `.ts`/`.tsx` under `07-frontend/src`: **523 files, 735 props declared in
`*Props*` types. 12 are never referenced again in their own file.** On inspection:

* **4 are false positives** — `Button.ButtonOwnProps.children` (React passes children by nesting; `G13`
  excludes it structurally for the same reason) and three regional props read wholesale through
  `useRegional(props)` (`DefinitionDetailPage` ×2, `OneTimeBillTab` ×1).
* **8 are genuinely declared-and-never-read.**
* **6 of the 8 are also supplied by a live caller** — the exact shape: the two `writeBlockedReason`
  above, plus `timeZone` and `dateFormat` on `ChargeCodesTab` and `DiscountsTab`, which arrive by
  **spread** (`PlansRatesPage.tsx:272,279` render `{...rest}`).
* **2 are declared and passed by nobody** — `RoutesCyclesTab.dateFormat?` (mounted with only `readOnly`
  and `client`, `SettingsPage.tsx:609`) and `PaymentsTable.onLoaded?`.
* **Only the two `writeBlockedReason` have a consequence a user can see today.** Neither
  `ChargeCodesTab` nor `DiscountsTab` nor `RoutesCyclesTab` renders a date at all, and nothing calls
  `onLoaded`.

**Recommendation, made rather than asked (law 13): do not build a gate for this.** Eight findings of
which six are inert is precisely the ratio `check_unwired_props.py`'s own docstring warns about —
*"a widened gate that fires on 40 legitimately-later props teaches people to add ALLOW entries, which
is how a gate stops being a gate"*. The two live ones are a defect row; the other six are recorded here
so the next lane meets the fact instead of the surprise.

---

## 4 · `NFR-3` — the registry serves an honest envelope over an unbounded query

Verified line by line on this tip, not taken from the document:

* `apps/assets/selectors.py:495` — `rows = list(qs.order_by(f"{prefix}{field}", "id"))`. **Every matching
  asset is materialised.**
* `apps/assets/api.py:117-121` — `paginator.paginate_queryset(rows, request)` then slices that Python
  list. **No `LIMIT` and no `OFFSET` reach SQL.**
* **Four filters then run in Python over the whole list**, in five list comprehensions —
  `f.assigned` (both directions), `f.test_due`, `f.premises_id`, `f.service` — and three of them call a
  **per-row** helper: `_current_assignment()` issues one query per asset (`:96-99`), `_premises_of()`
  issues that query *and* a metering seam call (`:699-704`), `_service_of()` a seam call (`:707-711`).

**The arithmetic is the argument.** At the top of the in-scope tier — T5, 40,000 accounts — a clerk
opening the registry filtered by premises would materialise every asset row and issue on the order of
two queries per row to return a page of fifty. At T7 (≤3,000) it is correct today, which is why it has
never hurt. Same shape as `DEF-PAY-4221` on `GET /outstandings`, which is open and names four other
endpoints; **the assets registry is not one of them** (grepped: `asset_list` appears in exactly one
register row, `DEF-AST-4734`, about a filter that was ignored). Filed here once, as an engineering
finding, so lane 1 does not file it again from the registry screen.

---

## 5 · The 49 stated absences — counted, and one number is wrong

**The total checks out.** Counting rows in the blueprint's own tables: **A 17 · B 13 · C 11 · D 1 ·
E 7 = 49.** Two rows spot-checked against the code and both hold — `assets.sub` is in all eleven
catalogues with **zero** render sites, and the technician help string renders exactly where it says.

**The split does not check out.** The document says *"7 carry a specification · 42 out of scope"* in two
separate places. Counting the Decision column of its own rows: **block A carries 7 specification ids and
10 out-of-scope; block E carries 4 specification ids and 3 out-of-scope.** That is **11 rows carrying a
specification and 38 out of scope**, not 7 and 42.

**How it happened is the interesting half, and it is the same failure the document already fixed once.**
Block E was written *after* A–D were counted; its four rows fold into specifications minted earlier
(`AST-B-19`, `AST-B-27` ×2, `AST-B-03`), and the totals line counts a folded row as out-of-scope while
calling it *"three of them folding"* — there are four. The earlier correction (recorded in §13:
*"B was counted as 14 and D was left out — two errors that cancelled"*) fixed the **total** and left the
**split**. Residue of the same thing: block B's intro still opens *"All fourteen are OUT OF SCOPE"* over
a heading that reads 13 and a table that holds 13.

**What a machine sees of all this: one gate, and it counts something else.** `G38` is the only check in
the repository that touches a stated absence, and it asks exactly one thing — that every `<ArrivesWith>`
node in the front end passes `tracks="<ID>"`, so the sentence expires when its question or defect closes.
It counts **75** such nodes product-wide, of which **11** cite an id. The assets module's 49 absences are
mostly catalogue strings and server refusals rather than `ArrivesWith` nodes — `features/assets` contains
exactly **one** — so G38 can see almost none of them, and it could never say whether one is *ruled*.

**Nothing here changes a ruling.** Every one of the 49 still has exactly one of the two outcomes the
document's judgement rule requires; what is wrong is the tally, and a lane quoting *"7 specifications"*
into a work plan would under-count the work by four rows.

---

## 6 · Withdrawn, struck, superseded and corrected — **the do-not-re-file list**

### 6.1 · Five findings the document made and withdrew

| The claim, as it was made | Why it is wrong | What a lane re-reading the source will see |
|---|---|---|
| *"The Map tab uses four native browser dropdowns"* — filed as a **B14 rule 8** violation | Withdrawn by running the app: all four compute to `appearance: none` through `.view select`, an ancestor rule the component never asked for. Re-filed as `AST-B-06`, a **fragility**, not a violation | **This is the one that will recur.** `AssetMapTab.tsx` still holds four raw `<select>`s (`:439`, `:453`, `:466`, `:482`) whose own class sets no appearance. The rule that saves them is `FormModal.css:411-432` — a different file, a different module's stylesheet |
| *"Search does not reach the server"* | The probe typed into `input[type=search]`**`.first()`**, which is the topbar's search. Re-run correctly, `q=E-500` landed in the URL and returned 10 rows. **Search works** | Any scripted probe that does not disambiguate the two search boxes will reproduce the false finding |
| *"The wizard's Continue refuses silently"* | It renders *"This step isn't finished…"* in a `role="alert"`. **Correct behaviour.** Residue: no `aria-disabled` — noted, not filed | A source read finds no `disabled` attribute and concludes the same wrong thing |
| *"A one-character search is silently dropped by the server"* | One character issues **no API call at all** — the client's own minimum stops it first. Downgraded to a note | `selectors.py` genuinely discards a term under two characters (`:475`), so the server half reads exactly as the withdrawn claim describes |
| *"Several as-built fields drawn with the helper in the right place"* | v1 **tidied** as-built drawings into the correct order. Measuring eighteen fields found ten wrong. The drawings now show the breach | — (a drawing fault, not a source fault) |

### 6.2 · Four specification numbers struck and **never reused**
`AST-B-07`, `AST-B-08`, `AST-B-09` (the import refusal copy, reopening a finished run, three inert
import sources — retired with the import runner on 2026-09-11) and `AST-B-17` (a registry-wide Work
orders tab, withdrawn the day it was drawn, by instruction: *"07 Work orders- remove this wireframe"*).
**The import tab and its five-stage runner are out of scope.** The registry draws seven tabs; the
blueprint covers six. That is scope, not a defect, and no lane files against it.

⚠ **One finding survives `AST-B-17`'s withdrawal and is worth keeping:** `GET /work-orders` takes six
filters and returns **400 on a seventh**, so a registry-wide work-orders tab could never have been a
query-string change.

### 6.3 · Five assumptions the document made and corrected — each looks true in the source
1. *"Repair cost is never captured"* — **false.** `Log repair` captures cost; the first read stopped
   short of the field.
2. *"The retire wizard has no Cancel"* — **false.** `WizardFrame` offers **Save & exit** and **Park**
   through an **optional** `exit` prop; six wizards pass it and both asset wizards pass none. *"Nothing
   can catch an unset optional prop, because that is what an optional prop is for."*
3. *"The Consumption panel was invented"* — **false.** It is `AssetUsageStrip`, mounted at
   `AssetDetailPage.tsx:1108`; the search looked for *chart*, *Consumption* and `KPIStrip` and the
   component is named none of them.
4. *"`GET /settings/services` is System-Admin-only"* — **false, and it is a permission taken from a
   comment.** It is `AnyTenantRole` (`apps/tenancy/api.py:420`, `services_settings`). The claim came from
   `AssetRegistryPage.tsx`'s `exceptions:` footer, written 2026-08-10 — **the same footer that also
   still claims the behind-the-meter *Exported* card is "always the stated dash"** while line 1000 of
   the same file renders the served rollup and the app shows 780 kWh. **Two bad claims, one footer, and
   nothing in this repository checks a footer against the code above it.**
5. *"Work carries no cost"* — **false.** `work_order_cost_lines()` totals labour plus parts under
   `BR-WRK-051`; it reaches the asset nowhere, which is `AST-B-21`.

### 6.4 · Three figures the document invented, and one pointer that does not resolve
The masthead and §13 both say *"the three figures it invented"*. **The document never itemises them.**
Its KPI row says *"Three v1 figures were fabricated … the row below says which"* and the row below is
about descriptions. The best available reading is the three KPI strips re-measured in this pass —
Meters `103 · 0 · 6 · 0`, Behind the meter `7 · 0 · 780 kWh`, Inventory `8 · $1,511.00 · 4` — but **the
old values are not recorded anywhere**, so no reader can check the correction. Separately and
explicitly fabricated: the R1 remedy's maintenance row (*06/02/2026 · Repair · Replaced the register and
resealed · Sam Reyes · WO-1042 · $84.00*) — **none of it real**; `asset_maintenance` holds zero rows and
no work order is anchored to an asset on this tenant.

### 6.5 · A ruling the document overturned, and four counts it corrected
* **Overturned:** the *Opening read* on the add wizard was recorded **out of scope** in v1 on a lane
  instruction about a missing seam; it is now `AST-B-14` on the instruction *"make opening read enable
  user can add reading"*, and `capture_final_read` turns out to be a **precedent** for that write rather
  than the blocker it was read as. A newer decision beats an older one; the old reasoning is struck,
  not deleted.
* **Corrected counts, all of which appear in older copies:** drawings `28` → **56**; specifications
  `12 · withdrawn 3` → **24 · withdrawn 4**; fields traced `174` → **137**; the absence split (see §5,
  still wrong).
* **Screens renumbered once, monotonically** (old 11→10 … old 26→25) after the import cut, and once as
  a **permutation** (old 07 became 19 while 19 became 17). **Specification ids did not move.** Cite the
  blueprint's *current* screen numbers only.

---

## 7 · Where this lane disagrees with the blueprint

### 7.1 · Two of the six missing descriptions are a PO ruling, not a defect
The blueprint's rule-18 row reads *"Zero of six are inside the budget, and two render nothing at all"*
and treats all six as one violation. **`AssetRegistryPage.tsx:796-801` says why the two are blank, and
it is a ruling:**

> *"(b) D9 RULED 2026-08-22 (B16 §10): r10 draws a KPI grid and NO prose on the Meters and
> Behind-the-meter tabs, so only Sub-meters keeps its caption … The other two keys stay in the
> catalogues."*

`04-docs/02-decisions/16-cr028-assets-design.md:739` records the ruling itself — **"D9 RULED — draw the
KPI grids"**, against the agenda item *"Confirm: drop the prose, draw the KPI grids."* Under the
blueprint's **own** judgement rule (*a recorded ruling that a thing waits makes it out of scope*), those
two are out of scope. **The real defect on those two tabs is that the grid which replaced the prose
renders four em-dashes — which is `AST-B-01`, already filed.** So the row should read **four of six over
budget** (9, 18, 23, 24 words) and two ruled.

⚠ **And the convention itself is not in B14.** *"Six to eight words"* is a PO instruction quoted in the
blueprint; grepping `04-docs` and `12-governance` for it returns **nothing**. B14 rule 33 caps by kind
(a fact ≤ 6 words, an instruction ≤ 6 per sentence) and rule 32 gives a screen a description budget.
A lane fixing these should cite **rule 33**, and whoever wants *six to eight* as a rule should put it to
the PO for a B14 row — not build to a number the rule set does not carry.

### 7.2 · The spacing count is *eight of ten on the scale* only because an off-scale value is on the good list
The blueprint's *"what did not go wrong"* list includes **KPI cell 16×20 gap 6**. **6 is not a step of
the scale that same section states** (4 · 8 · 12 · 16 · 20 · 24 · 32), and rule 39's KPI anchor was
amended to **8** on the day the blueprint was written. So there are **three** off-scale values, not two,
and the third is the only one that is not a long-standing product literal — it is a ratified anchor
missed by 2px. Filed.

### 7.3 · The rule-16 row is right and incomplete, and the finding is already twice filed
See §2.2. A lane reading only the blueprint would file a third row and would fix one of two footers.

### 7.4 · `AST-B-24` means two different things in two places
§13 says *"Variation by kind … New specification `AST-B-24`"*. **The register says `AST-B-24` is *"The
reads table pages on the server"***, and carries no variation-by-kind row at all. §13 likewise credits
`AST-B-19` to the reads-table pager while the register gives `AST-B-19` the three in-asset lists.
**The register wins** (the CR already rules that the table wins). A lane carrying `AST-B-24` from §13
into a defect row would file it against the wrong subject — which is the precise hazard this repository
never renumbers ids to avoid.

### 7.5 · Two blocks of the document sit outside every section
`</section>` closes section 10 at line 3271, **before remedies R5 and R6** (129 lines); and screens
**14 · Edit one asset** and **15 · Delete this asset?** sit between `</section>` at 1789 and
`<section id="s04b">` at 1855. The section rail the restructure pass added is drawn by
`section::before`, so it does not run beside any of them, and the fact/promise distinction the document
says is structural does not apply there. Cosmetic for a reader, load-bearing for a lane that navigates
by section.

### 7.6 · Its own section-09 table has twelve rows and its closing sentence says eleven
Counted mechanically. Same shape as its *"Twelve live specifications"* over a register of 24, which the
CR already records.

### 7.7 · B14 does not hold 38 rules, or 39, or 31 — it holds **30**
The blueprint's section 01 says *"38 binding UI rules"*. `CLAUDE.md` says **thirty-nine**. B14's own
still-live *PROPOSED* section says *"THE COUNT OF BINDING RULES IS THIRTY-ONE SINCE 2026-08-30"*.
**Counted from B14's own tables: rules 1–21 and 31–39 = 30 numbered rules.** 22–29 were never minted
(zero mentions in B14 and zero citations anywhere in the repository); 30 is deliberately unused because
its proposal was declined.

The honest reading is that `CLAUDE.md`'s number has always been the **highest rule number** rather than
a count — its own history (*"said twenty-nine while B14 held 30 … thirty-two while B14 held 34"*) reads
that way. That convention is nowhere written down, which is why a second document rounded it to 38 and
a third to 31. **This is the sixth time this pointer has been wrong**, and `CLAUDE.md` already says why:
*ratifying a rule and updating the pointer to it are two acts and only the first one feels like the
work.* Filed, with the recommendation that B14 carry the number once, in its own header, computed from
its own table.

---

## 8 · Journeys, boundaries and what did not go wrong

**Journeys (section 07).** Six defined, six walked, zero skipped; twelve surfaces opened directly and
every other screen marked UNVERIFIED in its own field table rather than graded on a read. **Zero failed
network requests across every asset screen in both walks** — no 4xx, no 5xx, no control throwing on
click. Two things the seed could not give: `seed_demo` reported a failed sample-data block for payments
and a `VAL-002` on a rating charge table; **neither touches assets**, and saying so is what stops a
later walk being quietly wrong. Nothing in section 07 is re-derivable here — **there is no running
stack to drive** (§10) — so those rows stand on the blueprint's evidence, which states what was done
and what happened for every one.

**Cross-module (section 11).** Eight crossings: six healthy, two *leaky by the letter*, **zero writing**.
Both leaks are named rather than hidden — `seams.unit_row` returns a model instance and all three
callers discard it (an existence probe), and the tenancy export kernel is imported directly rather than
through `seams.py`. Spot-checked here: **`apps/assets` writes no foreign model**, and the address rule
holds — `Asset` declares no address column and `assigned_address` is derived by walking to `premises`.
`G78` enforces the same property for Work; **no gate enforces it for assets**, so this one is true by
construction rather than by check.

⚠ **One structural fact the blueprint reports and this lane confirms: the module map names the wrong
directory.** `CLAUDE.md` puts assets under `metering`; every `/assets*` route is declared in
`apps/assets/api.py`. The module's own docstring calls it an Eng hosting disposition and says it was
reported for the daily PO batch. **Nobody has ruled that the map should change**, so it is recorded and
not corrected — but note that the defect register has used **both** `DEF-AST-` (7 rows, most recently
`DEF-AST-4734` on 2026-09-09) and `DEF-MET-` (71 rows) for this module. **This lane files `MET` per its
brief**, and flags the divergence so step 2 greps for both.

---

## 9 · Rows filed, rows deliberately not filed

**Filed from this lane.** Seven rows, appended one line each through `10-scripts/file_defect.py`
(never a `csv` writer), ids re-derived against the remote at filing time; `git diff --numstat` over the
register reads **7 insertions, 0 deletions**.

| id | what | why it is here and not on a screen lane |
|---|---|---|
| **`DEF-SHL-4946`** | B14 rule 13 — the shared table's sort never clears | `DataTable`, 54 consumers |
| **`DEF-SHL-4947`** | R11 title size — two sizes not split by kind, over a token comment that describes a default the component does not have | `PageHeader`, 137 mounts |
| **`DEF-SHL-4948`** | B14 rule 15's cap — 14 of 63 row-action blocks exceed two with no overflow | fourteen screens, one rule |
| **`DEF-SHL-4949`** | B14 rule 39's KPI anchor — `gap: 6px` where 8 is ratified | `components/KPIStrip.css`, every staff KPI strip |
| **`DEF-MET-4950`** | `BR-SHL-025` — `writeBlockedReason` declared, passed and read nowhere on two asset tabs | two asset files; the missing *gate* is product-wide and is argued against in §3 |
| **`DEF-MET-4951`** | `NFR-3` — the registry paginates a materialised list | `apps/assets/selectors.py` |
| **`DEF-4952`** | Three live documents state three different counts of B14's rules | no module owns it, so it keeps the bare `DEF-` form |

⚠ **The module segment is `MET`, per this lane's brief.** The register has used **both** for this module —
`DEF-AST-` (7 rows, most recently `DEF-AST-4734` on 2026-09-09) and `DEF-MET-` (71). Step 2 should grep
for both.

**Not filed, deliberately:**
* **B14 rule 16's pager** — `DEF-449` and `DEF-2449` are both open and both name it. A third row would
  be the duplicate this register has already been burned by.
* **The six inert declared-never-read props** (§3) — recorded here; no user-visible consequence.
* **Everything the blueprint withdrew** (§6) — by definition.
* **The two blank tab descriptions** (§7.1) — a PO ruling, not a defect.
* **`DEF-2453`'s staleness** (`RowActionsMore` now exists) — that is an edit to an open row, which
  step 1 may not make. Step 2 should correct it in the same commit as the fix.

---

## 10 · What this lane could not do, said plainly

**There is no browser here.** Nothing is listening on port 8401 from this worktree, and no Playwright
browser is installed (`~/.cache/ms-playwright` is empty). So **every claim above about *rendered*
output is either the blueprint's own Chromium measurement or a source fact, and each is labelled as
one or the other.** The two findings that need a browser before they are fixed are the title size
(§2.3) and the field anatomy (row 2 of §1).

That is not an aside. **The lane whose subject is *rules no machine checks* could not check them either**
— which is hard-won law 6 in its own terms: *no gate looks at rendered output; nine defects were found
by diffing the running app and by nothing else.* The audience for these screens is a clerk and a utility
admin at **1280 and 1440**, and neither width was verified by anybody in this step.
