# CR-092-BRC01 · step 1 · lane 4 — ACTIONS: moving it, fixing it, retiring it, raising work on it

**Screens 22–27** — Reassign · Log repair / maintenance · Retire (1 Reason & final read · 2
Replacement · 3 Book value) · Raise work order.
**Written:** 2026-09-11 · **Baseline:** `0a1a677d9`, re-checked against `789d558c8` · **Version on
screen:** `2.237.0`

> **Step 1 identifies. It fixes nothing.** No component, catalogue, route, stylesheet or test was
> touched by this lane. `git status --short` in this worktree reports one line, and it is the
> `07-frontend/node_modules` symlink.

---

## 0 · HOW THIS WAS CHECKED, AND WHAT IT COST

**The stack is this lane's own, on private ports.** The shared stack the brief named on **8401**
was not there — a TCP probe returned nothing on 8401 and nothing on 8000 — so one was built:

| what | how | evidence |
|---|---|---|
| database | the existing `smartbillhub` on local PostgreSQL 16, **no migrate, no seed, no write** | 338 rows in `django_migrations`; 220 assets (brazosbend 11, pine-hill 135, oak-ridge 74) |
| API | `manage.py runserver 127.0.0.1:8462`, `config.settings.local`, `JOBS_EAGER=false` | `GET /api/brazosbend/assets` → `401` unauthenticated, `200` signed in |
| SPA | `npx vite build` → `node server.mjs` on `:8463` with `API_PROXY_TARGET=http://127.0.0.1:8462` — the DEPLOYED same-origin join, per `11-smoke-stack.sh` | `built in 18.77s`; `spa: /api/* → 127.0.0.1:8462` |
| browser | `playwright-core` from `07-frontend/node_modules`, chromium under `/opt/pw-browsers` | every figure below is `getComputedStyle` or a DOM read, at **1440×1000 and 1280×1000** |

**Nothing in this walk wrote.** Every form was opened and read; no submit was pressed. The retire
wizard was stepped to 3 because **nothing in it writes until step 3's commit**
(`AssetRetireWizard.tsx:216-228` — one `onCommit`), and the commit was read and never pressed.

**The green suite, stated up front, because it is the finding under every finding below.**

| check | result |
|---|---|
| `npx tsc --noEmit` | **0 errors** |
| `npx vitest run src/features/assets src/features/work/RulesPage.test.tsx` | **8 files, 177 passed, 12 todo, 0 failed** |
| `python3 10-scripts/gates/run_gates.py` | **77 PASS · 43 FAIL · 3 SKIP — MERGE BLOCKED** |

**All 43 gate failures are the tip's, not this lane's** — the working tree carries no change of ours
(`git status --short` = the node_modules symlink alone), so there is nothing of ours for a gate to
see. The runner itself printed *"since the last recorded run: NOTHING TO COMPARE — no record existed
before this run"*, so it cannot date them for us; the clean tree is what dates them.

**Not one of the nine findings below is visible to any of those three checks.**

### What could NOT be checked, with the reason and the number

| what | why | number |
|---|---|---|
| **The Billing Clerk's own view of Log repair** — `AST-B-04`'s exact screen | brazosbend has **one** user and they are `system_admin`. `sam.reyes@sample.test` IS a `billing_clerk` on pine-hill and oak-ridge, but the password in `def-shl-4272-a-clerk-signs-in-and-clicks.mjs` is refused today and `must_change_password` is `t` for that row — signing them in means WRITING to a shared database, which step 1 may not do | 1 user at brazosbend; sign-in returned **`401 POST /api/pine-hill/auth/session`** |
| — **what was done instead** | the degrade branch is `techQuery.isSuccess`, so it was forced by **refusing `GET /users` at the browser** (`page.route` → 403) on the same screen, same session. That renders the identical branch a clerk gets, and is stated here rather than reported as a clerk walk | see §3 |
| **A tenant where a template applies AND the asset detail has a door** | no tenant has both | brazosbend has **0** `work_order_templates`; pine-hill has **8** and oak-ridge **4**, and neither detail page has a door either (measured) |
| **The R12 / rule-39 pixel gaps (29px / 47px)** | lane 3 owns the module-wide R12 measurement; this lane read **DOM order** only, to cross-check the field list | 8 of 15 `.field` elements on these screens (§4) |
| **The 36-word helper the blueprint names** | it is not on these four screens | worst here is **19 words**, twice |

---

## 1 · THE ONE THAT BLOCKS THE JOURNEY — `AST-B-02`

### The rule, verbatim, from `04-docs/05-modules/16-work/02-business-rules.md:152`

> **BR-WRK-056** | **The Assets door is ONE form with four ways in** — `/{tenant}/assets/{assetId}/work-orders/new`, a sibling of `…/maintenance/new` (`S53` · `AST-07`); **the action bar, the Maintenance history panel** and the four `RaiseWorkOrderCheckbox` ticks (Asset add · reassign · log maintenance · retire/replacement) all post it. ⚠ **AMENDED 2026-09-06 (`DEF-WRK-4125`) — NAME AND COUNT ONLY, THE RULE ITSELF IS UNCHANGED.** … It writes `work_orders.asset_id`; templates are filtered by *applies to asset types*. | **CONFIRMED — `WM-43`** | `US-WRK-038` TC-1…TC-7 |

**It is CONFIRMED. Two of the things it names have never been built.** A rule that is ratified and
unbuilt does not need re-signing; it needs building.

### What exists and what does not, each with its line

| the rule names | built? | where |
|---|---|---|
| the route itself | **yes** | `RaiseWorkOrderPage.tsx:71` · `App.tsx:1006` · registry `screenIds.ts:1301` |
| **the action bar** | **NO** | `AssetDetailPage.tsx:374-412` draws Assign/Reassign · Log repair · Retire · Delete, and nothing else |
| **the Maintenance history panel** | **NO** | `AssetDetailPage.tsx:1322-1330` draws the heading, the append-only note and **`+ Log repair`**, and nothing else |
| tick 1 · Asset add | yes | `AssetAddWizard.tsx:1017` → `:474` |
| tick 2 · reassign | yes | `AssetFlowPages.tsx:418` → `:294` |
| tick 3 · log maintenance | yes | `AssetFlowPages.tsx:659` → `:546` |
| tick 4 · retire / replacement | yes | `AssetRetireWizard.tsx:327` → `:220` |
| *(a fifth the rule does not name)* | yes | `AssetLifecycleTab.tsx:187`, the certification wrench |

```
$ grep -c raiseWorkOrderPath 07-frontend/src/features/assets/AssetDetailPage.tsx
0
```

### Measured in the browser, on two tenants, at both widths

| page | occurrences of *"Raise work order"* | `a[href*="work-orders/new"]` |
|---|---|---|
| brazosbend `M-7001` · Overview (installed) | **0** | **0** |
| brazosbend `M-7001` · `?tab=maintenance` | **0** | **0** |
| pine-hill `E-5024` · Overview (inventory) | **0** | **0** |

Identical at 1280 and 1440. The header's buttons on the installed asset are exactly
`Reassign · Log repair · Retire`; on the inventory asset, `Assign · Delete`. **The form is reached
only by typing its URL** — done, and it renders correctly with badge `WRK-24` and zero failed
requests.

### The four ticks are not a substitute, and this is the part worth reading

**Every one of the four ticks is POST-COMMIT.** `AssetFlowPages.tsx:294` and `:546`,
`AssetRetireWizard.tsx:220` and `AssetAddWizard.tsx:474` all navigate to the raise form **inside
`onSuccess`**, after the move, the repair or the retirement has already saved — deliberately, and the
reason is written at `AssetFlowPages.tsx:104-111`: *"a checkbox that raised a job as a side effect of
a move would raise one even when the move was refused."*

So the ticks answer *"while I am doing X, also send someone"*. **Nothing answers *"this needs a
visit"* on an asset a clerk is merely looking at** — which is the sentence the screen's own question
asks: *"This needs a crew. Can I raise the job from here without leaving the asset?"* The answer on
this tip is **no**, unless they first reassign, repair, retire or create the thing.

### What step 2 must DECIDE, and this lane does not decide it

`row_actions()` (`06-backend/apps/assets/selectors.py:214-224`, `BR-AST-006`) serves the action set
the header gates on: `view · edit · assign · delete · reassign · log_repair · retire`. **There is no
`raise_work_order` in it.** So the missing door is not purely a front-end omission, and there are two
lawful shapes:

* **key the control off the action set**, which means amending `BR-AST-006`'s served list — a rule
  change with a server edit; or
* **render it unconditionally**, which is defensible because the gate on this action is Work's own on
  `POST /work-orders`, not an assets-module gate (decision log 2026-09-05, *"apps/assets gains no
  line of code at all"*), and because `BR-WRK-056` names the action bar without qualifying it by
  state.

⚠ **A retired asset returns `["view"]` only.** Whichever shape is chosen must say what a TERMINAL
asset shows, because "raise a job on a retired meter" is a real thing a clerk might want (*take it out
of the vault*) and a real thing they should not be offered.

### Why no check caught it

`G100 every-screen-has-a-door` is **exactly** this check and it could never have seen this:
`REGISTER = 07-frontend/src/portal/routing/screenIds.ts` and `PORTAL = 07-frontend/src/portal`
(`g100_every_screen_has_a_door.py:144-145`). The staff app's register — the one that allocates
`WRK-24` — is outside its scope entirely. It reports its number truthfully over a scope it silently
excludes, which is hard-won law 7's fifth shape, named there in those words.

`G13` asks whether a prop is passed. Nothing in this repository asserts a control's **absence**.

---

## 2 · SCREEN BY SCREEN

### Screen 22 · Reassign — `/{tenant}/assets/{assetId}/reassign`

| | |
|---|---|
| **blueprint claims** | data captured complete; `service` correctly omitted; two date inputs with no bounds and no Today; the confirmation copy exists unrendered; `SERVED` |
| **verified** | opened at 1440 and 1280, rendered, **zero failed requests**. Title `Reassign M-7001` at **32px**. Two `input[type=date]` — `effective_date`, `final_read_date` — **`min: null`, `max: null` on both**, **0** Today controls. The segmented destination, the unit picker, *Record the final read* (on), *Move its sub-meters too*, and the work-order tick all render. Both consequence sentences render **beside** the form as `Note`s (`AssetFlowPages.tsx:424-425`) — the blueprint's "exists unrendered" is too strong: they render, in the wrong place |
| **missed** | `assets.reassign.recordFinalRead` reads *"Record the final read **before moving**"*; the blueprint's figure and prose both drop the last two words |
| **not checked** | the submit path, and therefore `BR-AST-022`'s 422 refusal. It writes |

### Screen 23 · Log repair / maintenance — `…/maintenance/new`

| | |
|---|---|
| **blueprint claims** | capture complete including **cost**; the fault is HOW the technician is captured; one date, no bounds, no Today; `DEGRADED` |
| **verified** | all of it. Cost **is** captured (`AssetFlowPages.tsx:646-655`, `§10-D3`, and no GL sentence anywhere). One `input[type=date]` (`date`), `min: null`, `max: null`, **0** Today. Title **32px**. As `system_admin` the technician field is a `SearchSelectField`; with `GET /users` refused it is `input[type="text"]` under *"Your role can't list users, so enter the technician's ID."* |
| **missed** | **three things** — (a) the degrade is keyed on `techQuery.isSuccess` with `retry: false`, so **any** failure fires it, not only a role refusal, and the sentence then states a cause that is false; (b) the field's label is `assets.maintenance.tech` = **"Assign tech"**, not "Technician" — `assets.maintenance.technician` exists but is the DETAIL page's table header, so a step-2 lane building the blueprint's *"shows **Technician** as a searchable picker"* would rename the wrong key; (c) `assets.maintenance.dateHelp` = *"Cannot be in the future."* is a stated bound the control does not enforce — the same shape the blueprint attributes to Retire, and on **this** screen it is true |
| **not checked** | the Billing Clerk's real session (see §0) |

### Screens 24–26 · Retire — `…/retire`, three steps

| | |
|---|---|
| **blueprint claims** | step 1 `SERVED`; **steps 2 and 3 `UNVERIFIED` — "not reached, the walk was scripted by address"**; two dates, no bounds; the `exit` prop unset on all three |
| **verified — INCLUDING THE TWO THE BLUEPRINT COULD NOT REACH** | stepped to 3 in the browser with no write. **Step 1:** title `Retire M-7001` **32px**; `retire_date` and `final_read_date`, `min: null`, `max: null`, **0** Today; the irreversibility box before the first field; footer is **`Continue` and nothing else**. Pressing Continue empty renders `role="alert"` *"This step isn't finished. Fill in what's marked above, then press Continue again."* and stays — **correct behaviour**. **Step 2 (now verified):** *Replaced by* with help *"Optional. The asset number of a living asset in this utility."*, the **fourth `RaiseWorkOrderCheckbox`** — *"Raise a meter-exchange work order for the swap"* — live and unconditional on that step, and the unmetered-seat warning *"Leaving Unit A unmetered puts its account onto estimated billing from the next cycle."* Footer `Back · Continue`. **Step 3 (now verified):** the honest no-cost state *"…there is no book value to compute, and nothing to write off"* with `data-book-value-absent`, and the commit **`Retire M-7001 ✓` in the danger tier** — `text-danger-700 border-danger-500`, `commitVariant="danger"` at `AssetRetireWizard.tsx:374`, which is `DEF-712` holding. Footer `Back · Retire M-7001 ✓` |
| **missed** | the blueprint's own **figure 30-equivalent for step 1 (figure 35) draws a `Cancel` in the footer. There is none.** Measured footer at step 1, both widths: `["Continue"]`. See §5.3 |
| **confirms** | `exit` is passed by **six** files and all six are customers or billing (`NewConnectWizard` · `MoveInWizard` · `TransferWizard` · `DisconnectWizard` · `MoveOutWizard` · `BillRunWizard`); `AssetRetireWizard` and `AssetAddWizard` pass none. That is `AST-B-28`'s territory, not a separate finding |
| **not checked** | step 3's commit. It writes, terminally |

### Screen 27 · Raise work order — `…/work-orders/new`

| | |
|---|---|
| **blueprint claims** | three keys and that is correct; no door; badge cites `WRK-19`; title 40px; the dead submit; `SERVED` |
| **verified** | badge renders **`WRK-24`**, so no user sees the wrong id. Title **40px at both widths**, against 32px on all four other screens in this lane. Consequence box renders. Submit `disabled: true`. Template `<select>` offers `Choose a template` and nothing else on brazosbend; on pine-hill it offers **8** templates and the submit goes `disabled: true → false` on picking one. Zero failed requests |
| **missed** | **(a)** brazosbend — the demo fixture's flagship tenant — holds **0** `work_order_templates`, so on the tenant every walkthrough uses, *"No template applies to this kind of asset"* is not an edge case, it is the **only** state this screen has; **(b)** the screen composes **no kit field at all** — `0` elements with class `.field`, and it imports nothing from `FormModal` (B14 rule 36); **(c)** its three utilities `border border-neutral-300 px-2 py-1` are **dead** — measured padding is `6px 30px 6px 10px` and the border is `--color-divider`, both from `.view select` (`FormModal.css:423`), which outranks a single-class utility. The control looks right because `AppShell.tsx:1011` wraps every screen in `<main className="view">`, not because this file styles it; **(d)** the screen has **no test file** (§3.6) |

---

## 3 · FINDINGS, BY SPECIFICATION

### 3.1 · `AST-B-02` — the two ways in that were never built → **FILED**

Section 1 above. **High.** This lane files the one row, scoped to the RULE and naming both surfaces,
so that lane 2's detail-screen sweep does not file a second for the same absence.

### 3.2 · `AST-B-04` — a clerk cannot name the technician without a UUID → **FILED**

```tsx
// AssetFlowPages.tsx:511-518
// `GET /users` is System-Admin-only, so a Billing Clerk — who MAY log a
// repair (BR-AST-038) — cannot read the tech list. …
const techQuery = useQuery({ queryKey: assetTechPickerKey,
  queryFn: () => getTenantUsers({ per: 100 }, client), staleTime: 5*60*1000, retry: false });

// AssetFlowPages.tsx:592-612
{techQuery.isSuccess ? <SearchSelectField … /> : <TextField id="tech_user_id"
   label={t("assets.maintenance.tech")} … help={t("assets.maintenance.techNoList")} />}
```

* `BR-AST-038` is **CONFIRMED** (PO R4 Q&A, 2026-08-08) and the service agrees —
  `services.py:1346` carries `@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-AST-038")`.
* `GET /users` is `SystemAdminOnly` (`apps/identity/api.py:194`).
* So **the one role this screen was written for is the one role it cannot serve**, and what it offers
  instead is a box whose value is a uuid — **B14 rule 31**, ratified by the PO on 2026-08-31 in the
  words ***"no Databse ID on screen - that is a rule"***.
* **There is no screen in the product where a Billing Clerk can look a technician's uuid up**, so the
  fallback is not a degraded path, it is an impossible one.

**And the sentence is wrong on a second path.** `techQuery.isSuccess` is false for a 500, a timeout
or an offline browser as readily as for a 403, and `retry: false` means one attempt. A **System
Admin** meeting a transient failure is told *"Your role can't list users"* — a statement about their
permissions that is false. Same twelve lines, same fix; recorded in the row so it is not lost.

**THE DECISION THIS WAITS ON, STATED AND NOT MADE.** A read a Billing Clerk is allowed to make: a
name-and-email list of the tenant's users, scoped to what a picker needs. **Four things are open and
all four are the PO's or a rule's, not a lane's:** (a) which roles may read it — every tenant role,
or admin + clerk; (b) whether it lists every user or only those who can be a technician, which is a
question about whether *technician* is a role, a crew membership, or free text; (c) whether it lives
in identity or is served through Work's crew list, given that Work owns crews and technicians per the
module map; (d) what the field does when even that read fails, since a text box holding a uuid may
not be the answer twice. **Nothing here is chosen by this lane.**

**Why nothing caught it — verified against the gates' own source, not assumed.** Rule 31 has four
enforcers and the shape *a field whose INPUT takes a uuid* is outside all four:

| enforcer | what it reads | why it misses this |
|---|---|---|
| `G28` | strings — eleven catalogues, backend prose, `raise` sites | its own docstring: *"a uuid-shaped VALUE in a field is the one thing G28 cannot see"* |
| `G69` | `<expr>.id.slice(` and an id joined next to a `·` in a template literal (`g69_id_slice_on_screen.py:46-77`) | nothing here slices and nothing joins. The uuid is **typed in**, not rendered out |
| `cr053-bill-surface.mjs` | rendered text, refusing a uuid | **`S30` alone** |
| `UnitPlanIdNeverShows.dom.test.tsx` | the frame-before-data case | **`S15` alone** |

### 3.3 · `AST-B-05` — the citation that points at a retired screen → **FILED**

**`WRK-19` appears in 6 files and 9 lines. Two are wrong. Four are the record of the retirement and
must not be touched.**

| file · line | verdict |
|---|---|
| `features/assets/RaiseWorkOrderPage.tsx:57` — `export const RAISE_WORK_ORDER_SCREEN = "WRK-19";` | **WRONG.** Imported by nothing — one grep hit across `07-frontend/src`, its own definition |
| `App.tsx:1006` — `// WRK-19` on the raise route | **WRONG.** A comment beside the route it mislabels |
| `routing/screenIds.ts:1308, 1492, 1583, 1584` | **correct.** These are the ruling itself: *"deliberately NOT `WRK-19`, which was retired in wave D — reusing a retired badge would make an old citation land on a screen it never named"* |
| `features/work/TemplatesPage.tsx:87` | **correct.** *"`WRK-19` was the blank page's row and retires with it"* — the screen it named |
| `features/work/AwaitingApprovalPage.tsx:100` | **correct.** *"the way `WRK-19` was minted for…"* — a minting precedent |
| `features/work/mobile/screenIds.ts:26` | **correct.** the same precedent |

⚠ **THE BLUEPRINT'S DONE-TEST FOR THIS ROW IS WRONG AND WOULD DESTROY THE RECORD.** Its register
says *"Checkable by grep: `rg "WRK-19" 07-frontend/src` returns nothing"*. Obeying that deletes the
four lines that exist **to stop exactly this defect recurring**. Its own section 13 gets it right —
*"A retired screen badge is written into **two files**"* — so here the register is the stale half and
section 13 is the accurate one. **The done-test is: two edits, `RaiseWorkOrderPage.tsx:57` and
`App.tsx:1006`, and `rg "WRK-19" 07-frontend/src` still returns seven lines in four files.**

`screenIds.ts:1301-1312` and `g29_allocated_badges.txt:182-188` both allocate `WRK-24` to this route,
and the screen renders `WRK-24` — verified in the browser at both widths. **Record-level only; no user
sees the wrong id.** Which is why it survives: `G29` checks that a route's badge is defined by an
authority, and a dead constant is not a badge.

### 3.4 · `AST-B-10` — the dead end → **FILED, and the blueprint's mechanism is wrong**

```tsx
// RaiseWorkOrderPage.tsx:167-190
{rows.length === 0 && (<p … data-raise-none="">{translate("assets.raiseWork.noneApply")}</p>)}
<Button data-raise-submit="" disabled={templateId.length === 0 || raise.isPending} …>
```

**Measured, both widths:** `{ disabled: true, ariaDisabled: null, title: null, describedby: null }`.

* **The submit is NOT enabled.** The CR's classification table says *"the submit stays enabled over
  nothing"* and the blueprint's register says *"disabled carrying that reason, **not enabled over
  nothing**"* — both read as though it is live today. It is not. The blueprint's own screen-27
  callout and States row say *"permanently disabled"*, which is right. §5.1.
* **What IS true, and it is the sharper statement:** the `disabled` expression reads `templateId`
  and **never reads `rows.length`**. The control is disabled by accident — because nothing can be
  selected — not because a refusal was stated. So it carries no reason: no `title`, no
  `aria-describedby`, nothing tying the greyed button to the sentence beside it. That is
  `BR-SHL-025`'s posture (*"disabled WITH its reason"*) missed by coincidence rather than by design,
  and a later change to the enable condition would silently produce a live submit over a refusal.
* **The dead end is the real cost.** Links out of this screen: the 13 rail items and `← Asset`.
  Nothing points at the Work templates screen, at a generic work order, or at anything a clerk could
  do next. On **brazosbend this is the only state the screen has** (0 templates), so a clerk on the
  demo tenant meets a sentence and a grey button, every time.

**The decision step 2 must make** — where the control goes: the Work templates screen (which is
admin-only, so a clerk would meet a second refusal), a generic template-less work order (which
`create_work_order` may or may not accept), or back to the asset. **Not made here.**

### 3.5 · B14 rule 7 — five dates, no bounds, no Today → **FILED against the KIT**

| screen | input | `min` | `max` | Today controls on the page |
|---|---|---|---|---|
| Reassign | `effective_date` | `null` | `null` | 0 |
| Reassign | `final_read_date` | `null` | `null` | 0 |
| Log repair | `date` | `null` | `null` | 0 |
| Retire 1 | `retire_date` | `null` | `null` | 0 |
| Retire 1 | `final_read_date` | `null` | `null` | 0 |

**Five inputs, three screens, both widths. `min` and `max` are absent because `DatePickerField`
has no such prop** — `FormModal.tsx:573-602` declares `id · label · value · onChange · prefill ·
dateFormat · required · help · error · disabled` and nothing else. **A `Today` control exists nowhere
in the product**: one `min=` on any date input across `07-frontend/src` (`FilterBar.tsx:328`, a range
end), and no button or link whose whole text is *Today* in the component kit.

⚠ **SO THIS IS A KIT GAP, NOT AN ASSETS DEFECT, AND THE ROW SAYS SO.** Filing it against these five
inputs would send a lane to patch three screens and leave every other date field in the product
exactly as it is. B14's own enforcement column for rule 7 is empty; no gate names it. Lane 6 reached
the same conclusion independently and filed nothing, so this lane files it once, against
`FormModal.tsx`, with these five as where it was measured.

⚠ **AND THE BOUND THE BLUEPRINT QUOTES IS NOT ON THIS SCREEN.** See §5.2.

### 3.6 · The raise screen has no test of its own → **FILED**

`RaiseWorkOrderPage.tsx:12` declares `Tests: src/features/assets/RaiseWorkOrder.test.tsx` and its
Lifecycle block at `:202` declares `gates: tsc✔ eslint✔ vitest (RaiseWorkOrder.test.tsx) …`.

```
$ find 07-frontend -name "RaiseWorkOrder*.test.*" -not -path "*/node_modules/*"
$ git log --all --oneline -- '07-frontend/src/features/assets/RaiseWorkOrder.test.tsx'
```

**Both empty. The file has never existed on any branch.** It is parked at
`10-scripts/gates/g116_missing_test_citations.txt:56`, one of the 65 baselined on 2026-09-06 when
`G116` was written, and has not moved since.

**The `Tests:` half is a known, tracked gap. The `gates:` half is not, and it is the stronger claim:
it says a run happened.** Nothing in this repository reads a Lifecycle `gates:` line, so a lane
deciding whether this screen is guarded reads *"vitest ✔"* and writes no case. The screen's only
coverage is `features/work/RulesPage.test.tsx`, which asserts the ROUTE five ways and nothing about
the SCREEN — so **the refusal state, the disabled submit, the consequence box, the `asset_no` kicker
and the mutation are all untested**, and §3.4 is precisely one of them.

---

## 4 · `AST-B-13` AND `AST-B-26` — measured, and DELIBERATELY NOT FILED

**R12 / B14 rule 39 · field order.** Read from the DOM, not from source:

| screen | `.field` elements | `label → helper → input` | no helper |
|---|---|---|---|
| Reassign | 5 | **3** — Effective date, Final register reading, Read date | 2 |
| Log repair | 6 | **3** — Date, Set status, Estimated cost | 3 |
| Retire 1 | 4 | **2** — Retire date, Final read | 2 |
| Raise work order | **0** | — | — |
| **total, this lane** | 15 | **8** | 7 |

That is exactly the eight the blueprint names on these screens; its 18 adds the add wizard's Asset #
and Service (lane 3's). **The order is not written on these screens at all** — it is fixed inside
`FormModal.tsx` at lines **241, 311, 363, 624 and 786**, all five field variants, so every helper in
the staff app renders this way.

⚠ **IT IS ALREADY FILED: `DEF-SHL-4921`**, 2026-09-11, *"THE STAFF FORM KIT PUTS THE HELPER TEXT
BETWEEN THE LABEL AND THE INPUT…"*, naming those exact five lines. **B14 rule 39's own status cell
records it too.** A `DEF-MET-` row here would be a second id for one fault in one shared file.
**Step 2 fixes `FormModal.tsx` and these eight move with it.**

**Helper length.** On the four action screens, **8 of 11 helper strings run over ten words**; the
worst are 19 (`assets.reassign.finalReadHelp`, `assets.retire.finalReadHelp`), then 16, 16, 12, 12,
12, 11. The three inside ten are `assets.maintenance.dateHelp` (5), `assets.retire.dateHelp` (7) and
`assets.maintenance.techNoList` (10).

⚠ **NOT FILED, AND THE BUDGET THE BLUEPRINT USES IS NOT A RULE.** *"Six to eight words"* appears
nowhere in `04-docs` or `12-governance`. **The citable cap is B14 rule 33** — an INSTRUCTION is
≤ 6 words **per sentence**, ratified 2026-08-30, with *"two sentences of six beat one sentence of
twelve"* — and `G33` enforces it for refusals only, against a baseline of 606 that may only shrink.
Lane 3 owns the module-wide count; **this table is a cross-check for lane 3's document, not a second
row.**

---

## 5 · WHERE THIS LANE DISAGREES WITH THE BLUEPRINT

**Seven, and the first three change what a step-2 lane would build.**

### 5.1 · `AST-B-10` — the submit is disabled today, not enabled
The CR's classification table (*"the submit stays enabled over nothing"*) and the register's
what-done-looks-like (*"disabled carrying that reason, not enabled over nothing"*) both imply a live
control. Measured `disabled: true` at 1280 and 1440, and `RaiseWorkOrderPage.tsx:179` is
unambiguous. The blueprint's screen-27 States row and callout are the accurate half. **The finding
survives in a better form** (§3.4): the disable does not READ the refusal, and there is no way
forward — which is what *"the control does not read it"* was reaching for.

### 5.2 · Retire's help does NOT state the install-date bound
The blueprint says twice — J4's date row and screen 24's Walked row — *"the retire step's own help
says the date **cannot be before the install date**"*. It does not. `assets.retire.dateHelp` renders
**"Any current assignment closes on this date."** The install-date sentence is
`assets.retire_before_install` = *"The retire date can't be before the install date."*, a **server
refusal** raised at `apps/assets/services.py:1516` (`VAL_RANGE`). The blueprint drew a help line the
product does not have — **B14 rule 37: a figure is an illustration, never a fact to build to.**
⚠ The claim is true of a **different** screen: `assets.maintenance.dateHelp` = *"Cannot be in the
future."* is a real stated bound the control does not enforce. The rule-7 row carries that version.

### 5.3 · Figure 35 draws a `Cancel` on retire step 1 that does not exist
Measured footer, step 1, both widths: **`["Continue"]`**. The blueprint's correction callout says its
earlier reading *"the retire wizard has no Cancel"* **"was wrong"** — on what a person sees it was
**right**; what was wrong was the reason it gave. `WizardFrame`'s escape is the optional `exit` prop
and this wizard passes none, so there is no Cancel, no Save & exit and no Park. The only way out of
step 1 is the header's `← Asset` link. Keep `AST-B-28`'s finding; drop the sentence that says the
original reading was mistaken.

### 5.4 · `AST-B-05`'s done-test would delete the record of the ruling
§3.3. `rg "WRK-19" 07-frontend/src` **must not** return nothing. Two files are wrong; four hold the
retirement ruling and the minting precedent.

### 5.5 · The technician degrade is not role-scoped
The blueprint frames it as *"for a Billing Clerk the picker cannot load"*. The branch is
`techQuery.isSuccess` with `retry: false` — any failure, any role. §3.2.

### 5.6 · The field is labelled "Assign tech", not "Technician"
`assets.maintenance.tech` = **"Assign tech"** is what renders; `assets.maintenance.technician` =
"Technician" is `AssetDetailPage.tsx:1339`'s table header. The blueprint's redrawn figure and its
register row both say Technician. A step-2 lane building to the register would edit the detail page's
column heading.

### 5.7 · Section 09's Screens column does not match sections 05 and 12
Section 09 lists the R12 and rule-7 rows against screens **"16–19, 20, 21, 22, 24"**, while naming
the fields of *the add wizard, reassign, log repair and retire* — which are screens **28–32, 22, 23,
24** in the same document, and 16–21 are the Edit screens. A lane keyed off section 09 goes to the
wrong screens. **Sections 05 and 12 agree with each other and with the code; section 09's column is
the stale one.**

### And one the blueprint could not do, now done
**Retire steps 2 and 3 were `UNVERIFIED` — "not reached, the walk was scripted by address".** Both
are now walked (§2), because nothing in that wizard writes until step 3's single commit. Everything
the blueprint inferred from source is confirmed, including the fourth `RaiseWorkOrderCheckbox` being
unconditional on step 2 — which is `DEF-WRK-4122`'s correction holding, seen rather than read.

---

## 6 · PROPOSED ROWS

Six, all `--id-module MET`. Ids are allocated against the remote at push time.

| id | what | spec | severity | surface |
|---|---|---|---|---|
| **`DEF-MET-4976`** | `BR-WRK-056` is CONFIRMED; the action bar and the Maintenance history panel were never built | `AST-B-02` | **high** | `AssetDetailPage.tsx:374-412` and `:1322-1330` · `selectors.py:214-224` |
| **`DEF-MET-4977`** | A Billing Clerk logging a repair is asked to type a uuid; the help states a cause that is false on every non-403 failure; and the label is the wrong key | `AST-B-04` | medium | `AssetFlowPages.tsx:511-518, 592-612` |
| **`DEF-MET-4978`** | `RAISE_WORK_ORDER_SCREEN` and `App.tsx`'s comment name a retired badge | `AST-B-05` | low | `RaiseWorkOrderPage.tsx:57` · `App.tsx:1006` |
| **`DEF-MET-4973`** | The raise form's disabled submit never reads the refusal, and the refusal has nowhere to go | `AST-B-10` | medium | `RaiseWorkOrderPage.tsx:167-190` |
| **`DEF-MET-4974`** | B14 rule 7 — the kit's date field has no `min`/`max` prop and the product has no Today control (module `platform-shell`) | — (J4) | medium | `components/FormModal.tsx:573-645` |
| **`DEF-MET-4975`** | The raise screen's `gates:` line claims a vitest run over a file that has never existed | — | low | `RaiseWorkOrderPage.tsx:12, 202` |

⚠ **THREE OF THESE WERE RENUMBERED AT PUSH TIME AND THAT IS THE LAW WORKING.** The allocator first
returned `4967`, `4971` and `4972`; lanes 2 and 3 pushed rows carrying all three while this lane was
still writing. `allocate.py defect --verify` caught it — *"TAKEN — a sibling pushed it"* — the
register was re-derived from the pinned tip, and only this lane's own bytes were renumbered to
`4976`, `4977`, `4978`. The prefix was then proved byte-identical to the tip, so no sibling row can
have been reverted. `DEF-MET-4973/4974/4975` were verified free and kept.

**Cross-lane note on `DEF-MET-4977`:** the row it displaced is lane 3's, and lane 3's own `4971` and
`4972` are about `AssetFormModal`'s submit and `PATCH /assets/{id}`'s unwritable fields — different
screens, no overlap with this lane's.

**Not filed, deliberately, and each says why above:** `AST-B-13` / R12 (`DEF-SHL-4921` owns it,
kit-wide) · `AST-B-26` helper length (lane 3's count; and the blueprint's budget is not a B14 rule —
33 is) · the 40px title (lane 6 filed `DEF-SHL-4947` against `PageHeader`) · `AST-B-28`'s unset
`exit` (a change, not a defect, and the blueprint carries it).

### ⚠ `DEF-MET-4976` IS A DUPLICATE OF LANE 2's `DEF-MET-4965` — amended after both landed

This section first told lane 2 not to file a second row for `AST-B-02`. **Lane 2 filed first**
(`DEF-MET-4965`, *"BR-WRK-056 is CONFIRMED and names the action bar and the Maintenance history
panel … neither exists on the asset detail page"*), and this lane's `DEF-MET-4976` is the second
row, not the first. The instruction is corrected here rather than deleted, because the mistake is the
useful part: **two lanes were each told they owned a different half of one absence, and both filed
it.**

**Step 2 should close `DEF-MET-4976` as a duplicate of `DEF-MET-4965`** and keep, from this row, the
two things lane 2's does not carry: the server-side decision (`row_actions()` names no raise action,
so `BR-AST-006`'s served list is either amended or the control renders unconditionally, and a
TERMINAL asset returns `["view"]` only), and the reason the four ticks are not a substitute (all four
navigate from inside `onSuccess`, after the write).

**And lane 2 found something this lane did not, which is worth more than either row.**
`07-frontend/src/features/assets/AssetDetail.test.tsx:807-812` asserts
`expect(html).not.toContain("Raise work order")` on the maintenance tab, under the comment *"No wo
storage exists yet (Work is R5)"* — **a green test holding the door shut, written when Work was
R5 and left standing when CR-070 wave M landed on 2026-09-05.** Verified on this tip. It is hard-won
law 2's mirror wearing a test's clothes: adding the control `BR-WRK-056` requires makes a passing
test fail, so a step-2 lane doing the right thing meets a red suite and could reasonably conclude it
was wrong. **Read lane 2's `DEF-MET-4966` before touching `AssetDetailPage.tsx`.**
