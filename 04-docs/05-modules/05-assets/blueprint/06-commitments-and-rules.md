# Assets blueprint — the 24 specifications, the rule violations, the remedies, the absences

**What this file is.** Lane F of the six-lane Assets audit. The other five lanes own
groups of screens; this one owns the cross-cutting sections of
`05-prototype/01 Assets Menu Blueprint.pdf` — **§08** (49 stated absences, pp. 128–134),
**§09** (rule violations, pp. 135–138), **§10** (remedies R1–R6, pp. 139–151),
**§11** (the module boundary, pp. 152–155), **§12** (the 24 specifications, pp. 156–160)
and **appendices G · H · K** (pp. 194–195, 209–210).

**How it was read.** Every page above was rendered to PNG with
`python3 10-scripts/pdf/pdf_render.py "05-prototype/01 Assets Menu Blueprint.pdf" <out> 4 <pages>`
and **opened as an image**, per B14 rule 42 (PO 2026-09-13: *"When you use images to
create screens your accuracy is higher; hence dont create screens using only Text"*).
Pages 128–161, 194–195 and 209–210 were read this way. The text layer was not used for
any claim in this file.

> ⚠ **PO clarification, 2026-09-13, binding: the PDF is the only source.**
> `04-docs/05-modules/05-assets/wireframes/CR-092-assets-screens.html` and
> `04-docs/05-modules/05-assets/08-screen-layouts.md` are **derived copies** of those
> wireframes and are second copies free to drift (hard-won law 5). **Neither was opened
> for this file.** Two shipped source files nonetheless cite them as *the drawing* in
> their Trace blocks — `AssetEditPage.tsx:4-7` and `AssetPanelEdits.tsx:7-8` — which is
> worth a row for somebody, because a Trace pointing at a derived copy is how the next
> lane gets sent to the wrong place.

**The other half of the job: the status column.** §12 ships every one of the 24 rows at
**Unverified**, and p157 says that is not a hedge — *"Engineering fills the column in
from the code, one row at a time, and on a module this well documented several will come
back already done."* The document was read at **`2.234.17`** on 2026-09-10 and
re-measured 2026-09-11. The product is at **`2.261.3`** today. **Twenty-seven
change-level versions have landed in between, and most of them are this work.**

---

## 0 · The headline

| Verdict | Count | Which |
|---|---|---|
| **ALREADY DONE** | **17** | `AST-B-01` `-02` `-03` `-04` `-05` `-10` `-12` `-13` `-14` `-16` `-19` `-20` `-21` `-22` `-24` `-25` `-27` |
| **PARTLY DONE** | **4** | `AST-B-11` `-15` `-18` `-28` |
| **NOT DONE** | **3** | `AST-B-06` `-23` `-26` |
| **BLOCKED** | **0 outright** | but the *remainder* of `-15` and of `-28` is blocked — see their rows |
| | **24** | |

**Seventeen of twenty-four are already built.** The document's own prediction was right
and then some. What is left is three pieces of real work (`AST-B-23`, `AST-B-26`, and the
Lifecycle download half of `AST-B-11`), one deliberate deferral to a kit-wide decision
(`AST-B-06`), one ruling to put to the PO (`AST-B-15`), one column (`AST-B-18`) and one
migration plus a screen (`AST-B-28`).

**And one new live defect was found doing this pass, which nothing in the document
predicts — see §7.** `GET /assets/lifecycle` gained server-side windowing and the front
end never asks for it, so the Certifications & tests due tab silently shows the first
fifty rows and its pager reports that as the total.

---

## 1 · The 24 specifications, with a verdict and what was read to reach it

`AST-B-07`, `-08`, `-09` **and `-17`** are struck and must never reach a build plan.
`-07/-08/-09` covered the import runner, out of scope by instruction 2026-09-11; **`-17`
(a registry-wide Work orders tab) was withdrawn the day it was drawn** — p159 carries its
WITHDRAWN row, quoting the instruction *"07 Work orders- remove this wireframe"*. So the
series runs `AST-B-01`…`-28` **minus four** = **24 live**, which is the arithmetic the
coordinator's note gives and which the PDF's own §12 table shows on pp. 158–159.

| ID | What it delivers | Screens | What the doc says it waits on | **Verdict** | What I read to decide |
|---|---|---|---|---|---|
| **AST-B-01** | The registry's KPI figures are served, not counted on the page | 01, 02, 03, 04 | Nothing but the work — a rollup per tab, or the count on the list envelope | **ALREADY DONE** | `selectors.asset_kpis()` (`06-backend/apps/assets/selectors.py:731`) serves the whole tab's population; `api.py:144-146` hangs it on the `GET /assets` envelope as `kpis`; `AssetRegistryPage.tsx:866-882` prefers the served pair and keeps the client count only as a fallback. Inventory's strip was already served from `GET /assets/stock` (`selectors.py:2338`, rendered at `AssetInventoryTab.tsx:113`). Sub-meters draws no strip at all, so there is nothing to serve there. `DEF-MET-4953`, PO 2026-09-12 *"a) Fix the figures"*, shipped `2.237.5` |
| **AST-B-02** | Raising a work order from the asset, from the controls the rule already names | 12, 27 | `BR-WRK-056` is CONFIRMED and names both controls | **ALREADY DONE** | `RaiseWorkOrderControl` (`AssetDetailPage.tsx:286-305`) mounted at **three** sites — the header action bar `:509`, the Open work panel `:1965` and the attention strip `:817`. Not gated by `hasAction()` on purpose (three reasons written out at `:224-250`); refused-but-visible via `raiseWorkRefusal` (`:270`) under `BR-AST-534`, PO 2026-09-12 *"a) Show it disabled, with the reason"*. `DEF-MET-4965`, `2.237.6` |
| **AST-B-03** | The utility service is picked from the tenant's enabled list, not typed | 28 | Nothing. `GET /settings/services` is `AnyTenantRole` and already serves the list | **ALREADY DONE** | `AssetAddWizard.tsx:718-749` builds `serviceOptions` from that endpoint through `enabledServiceRows()` and renders a `SelectField`. The wizard's own Trace records the correction: the old exception claimed the route was System-Admin-only and *"that is FALSE and was false when it was written"* — `apps/tenancy/api.py:419` is `AnyTenantRole`. `DEF-MET-4980/4981/4982`, `2.237.3` |
| **AST-B-04** | A billing clerk logging a repair can name the technician without a UUID | 23 | A role-safe read of the crew | **ALREADY DONE** | `AssetFlowPages.tsx:604-617` now reads **`GET /work/crew-directory`** (name + email only) instead of `GET /users`, and records the measurement on a real Billing Clerk session on `pine-hill`, 2026-09-12: `GET /users` → **403 `BR-IDN-009`**, `GET /work/crew-directory` → **200 · 7 rows**. `GET /users` was **not** widened. `2.237.4` |
| **AST-B-05** | A citation that points at a screen that exists | 27 | Nothing but the edit | **ALREADY DONE in substance — and the document's own check is invalid** | `routing/screenIds.ts:1345` mints the route `WRK-24` with the reason written out; `App.tsx:1091-1095` records that the comment read `WRK-19` until 2026-09-12 (`DEF-MET-4978`). ⚠ **The prescribed check — *"Checkable by grep: `rg "WRK-19" 07-frontend/src` returns nothing"* — returns 8 hits today**, every one of them prose explaining that `WRK-19` is retired. The check goes red on a correct fix, which is hard-won law 7's *output that cannot distinguish pass from fail*. Do not re-run it; read the two files instead |
| **AST-B-06** | The Map tab's dropdowns look like the product's | 06 | Nothing. The rule exists and the class is one word | **NOT DONE — deliberately deferred, with the reason recorded** | `AssetMapTab.tsx:429-457` — `DEF-MET-4959` **removed six utilities that were inert** (measured on the element in Chromium at 1440: `min-h-8` declared 32px / rendered 36, `px-2 py-1` declared 4/8 / rendered 6 30 6 10, `text-sm` declared 12 / rendered 14). That is a real fix and a different one. **The specification's own done-test is explicitly still unmet** and the file says so: *"the chevron and the height still come from an ancestor these controls never ask for, so renaming that wrapper restyles them silently. That is true of EVERY `<select>` in the product … a kit-wide question and not this component's to answer inside an Assets pass."* Needs a kit decision, not an Assets commit |
| ~~AST-B-07~~ | ~~The import refusal's stale copy~~ | — | — | **WITHDRAWN 2026-09-11** | Do not put this in a build plan |
| ~~AST-B-08~~ | ~~Reopening a finished import run~~ | — | — | **WITHDRAWN 2026-09-11** | Do not put this in a build plan |
| ~~AST-B-09~~ | ~~Three import sources that do nothing~~ | — | — | **WITHDRAWN 2026-09-11** | Do not put this in a build plan |
| **AST-B-10** | A clerk told no template applies is not left on a dead submit | 27 | Nothing. The refusal copy exists; the control does not read it | **ALREADY DONE** | `RaiseWorkOrderPage.tsx:205-245`. The refusal is **two sentences** (`noneApply` + `noneApplyNext`, B14 rule 33's *two sentences of six beat one sentence of twelve*), the submit reads `disabled={noneApply \|\| templateId.length === 0 \|\| raise.isPending}`, and it is joined to the sentence by `title` **and** `aria-describedby`. The code names the sharper finding: the submit had measured `disabled: true` before, but only *by coincidence* — nothing could be selected — so `BR-SHL-025`'s posture was satisfied by accident. `DEF-MET-4973`, `2.237.4` |
| **AST-B-11** | What is falling due can be sorted and searched | 05a, 05b, 05c | Nothing but the work — three served lists with no toolkit | **PARTLY DONE** | `AssetLifecycleTab.tsx` was **rebuilt 2026-09-12** (`DEF-MET-4955`, `2.237.5`) as three sub-tabs on the shared `DataTable`: search, filter chips, sortable headers (`sortable: true` on 11 columns), column selector, pagination footer, empty states, each section its own address via `?section=`. Certifications default to due, oldest lapse first. ⚠ **The DOWNLOAD the done-test names is absent.** `ListExportButton` is imported by `AssetRegistryPage.tsx` only, and `DataTable.tsx` declares no export control at all (`grep -c "ListExportButton\|onExport\|exportKind"` → **0**). ⚠ Also still true and named in the file: no first/last page control (out of scope to `CR-093` by PO ruling 2026-09-12) |
| **AST-B-12** | An asset can be corrected from the asset, at an address | 08, 14 | A route. `PATCH /assets/{id}` already validates a partial payload | **ALREADY DONE** | `AssetEditPage.tsx` (507 lines) exists; the route `assets/:assetId/edit` is registered at `App.tsx:1105`; **both doors** point at it — the header `Edit` (`AssetDetailPage.tsx:539`) and the registry pencil (`AssetRegistryPage.tsx:672-681`, which now navigates rather than opening a dialog). `AssetEditAddress.dom.test.tsx:343` asserts the address and both doors. PO ✅ approved 2026-09-12, `2.239.9` |
| **AST-B-13** | Every hint says which input it belongs to | 14, 16–21, 23 | Nothing. It is the order of two elements inside a field wrapper | **ALREADY DONE** | `FormModal.tsx` — all five help-bearing variants render **label → input → helper**, the helper as `<p className="field-help mt-1.5 mb-0">` *after* the control (`:301`, `:387`, `:429`, `:786`, `:1018`). `components/fieldAnatomyOrder.dom.test.tsx` pins the DOM order in all six kit sites (proved red at the pre-fix tip `a0b28104a`). `10-scripts/render-checks/cr092-lane3-field-anatomy.mjs` measured the figures in Chromium at 1280 **and** 1440 over 29 fields on five asset screens: label→input **5px** on 18/18, input→helper **6px** on 18/18, field→field **20px** on 11/11. `2.237.1` |
| **AST-B-14** | A meter booked in can record the reading it was installed at | 29 | *"Nothing. The column exists and the service takes it"* (§12) / *"A create-time read seam"* (R5's card — the two disagree) | **ALREADY DONE** | The seam was the thing that did not exist, and it does now: `metering/services.py:10188 capture_opening_read` published beside `capture_final_read`; `apps/assets/seams.py:391` resolves it; `services.py:1026 _capture_opening_read` is called from `_create_asset_inner` at `:1208`, **inside the create's own transaction**, so a refused reading takes the asset with it. Step 2 of the wizard carries an enabled `opening_read` + `opening_read_date` and refuses a reading with no date (`openingReadNeedsADate`, `AssetAddWizard.tsx:350`). PO 2026-09-12: *"Build it as drawn - move it to step 2, beside the multiplier, register digits and the warning"*. `2.237.10` |
| **AST-B-15** | Every screen in the list says what it is for, in a line a clerk can read | 01, 02, 03, 04, 05a, 05b, 05c, 06 | Nothing. The slot exists in `PageHeader` and two tabs pass nothing to it | **PARTLY DONE — and the remainder is BLOCKED on a ruling** | **Four were cut on 2026-09-12** (`DEF-MET-4961`, `2.237.5`), measured on `en.json` at HEAD: sub-meters **24 → 5** words, inventory **18 → 6**, lifecycle **9 → 6**, map **23 → 5**. ⚠ **Meters and Behind the meter still render nothing** — `AssetRegistryPage.tsx:812` reads `explainer: id === "sub_meters" ? t(...) : undefined` — and that is **D9, ruled 2026-08-22** (B16 §10: r10 draws a KPI grid and NO prose on those two tabs). The done-test *"No tab shows nothing"* therefore **contradicts a recorded ruling**, which is B14 rule 41's one legitimate question. It goes to the PO with both sides quoted; it is not a build. ⚠ The two strings survive in **11 of 11** catalogues and reach no screen — a second dead-copy row beside group D's |
| **AST-B-16** | The two facts the Overview shows that no column serves | 08 | A decision about where each is computed | **ALREADY DONE** | `_asset_cost_rollup()` (`selectors.py:998`) hung on `asset_dict()` at `:1156`, carrying `maintenance · work · lifetime · jobs_costed · open_work_orders · currency`; typed as `AssetCostRollup` (`endpoints.ts:8451-8457`) with `null` kept distinct from `0` on all three money keys and `open_work_orders: 0` deliberately a measurement. Rendered at `AssetDetailPage.tsx:1144`. `AssetOverviewPanels.dom.test.tsx:368`. `2.237.9` |
| ~~AST-B-17~~ | ~~A registry-wide Work orders tab~~ | — | — | **WITHDRAWN 2026-09-11, the day it was drawn** | p159's own row, quoting *"07 Work orders- remove this wireframe"*. Do not put this in a build plan |
| **AST-B-18** | The asset's work list carries the fields the wire already sends | 12 | Nothing on the server — the endpoint serves 29 fields and the client type declares four | **PARTLY DONE** | `OpenWorkPanel` (`AssetDetailPage.tsx:1868-1958`) renders the rows instead of discarding them (`DEF-MET-4967`, `2.237.6`) — no extra call was added; **Due** (`due_at`) and **Assigned to** (`technician`, reusing `dispatch._holder`) both carry values. ⚠ **Priority is still not a column.** It *is* now on the wire: `_scoped_row` gained `priority` and `source` under the Accounts pass (`work/selectors.py:449-450`), and `asset_door.orders_for_asset` runs through `selectors._scoped_page` → `_scoped_row`. So the spec's *"waits on nothing on the server"* is **true today and was false when it was written** (step 1 filed it as such). One column of browser work remains |
| **AST-B-19** | The three lists inside an asset page on the server | 09, 11, 12 | Nothing but the work — both endpoints return a bare list and fold the history in Python | **ALREADY DONE** | All three use `StandardPagination`: assignments `api.py:259-262`, reads `:280-282`, maintenance `:304-306`. The front end reads the envelope through the one declaration in `src/api/paginated.ts` (`readListPage`), never by describing the reply by hand. `AssetPagedLists.dom.test.tsx` drives a **stub `ApiClient` with the recorded server body** rather than seeding the cache — the file explains that a fixture that never crosses the boundary cannot see a boundary change. `2.237.8` |
| **AST-B-20** | The export a person presses actually downloads a file | 01, 02, 03, 04 | ~~A volume the worker and the web container share~~ ⚠ **SUPERSEDED 2026-10-02: the file is stored in S3 at `t/<web name>/export/…` and found through a database row — no volume (PO: *"Removed -> Yes we will just be using S3"*, `DEF-MET-4954` closed)** | **ALREADY DONE** | `docker-compose.yml` now declares a top-level `volumes:` / `artifacts:` (`:892-893`) mounted at `/app/var/artifacts` on **backend, celery and celery-billing** (`:130`, `:329`, `:461`) — I checked the compose file, not the register. `DEF-MET-4954` is closed at `2.237.5`, and the runbook trigger was corrected from `desiredCount > 1` to `JOBS_EAGER`, which is the true trigger. Two unreported downloads (the bill print set, the audit-log export) were broken identically and are fixed by the same change |
| **AST-B-21** | One asset, one cost — the two that exist today never meet | 12 | A decision about which cost an asset shows, and where the arithmetic lives | **ALREADY DONE** | The decision was made and ruled: PO 2026-09-12, *"a) One lifetime figure, both halves named beneath"*. `cost_rollup.lifetime` is the sum of the two **displayed** halves, each rounded first (`BR-WRK-051`: *"the total is the sum of the ROUNDED displayed lines"*), because they sit directly beneath it and a clerk who adds what they can see must get what they are shown. Work's half comes through `work/asset_door.cost_rollup_for_asset` and `assets/seams.work_cost_rollup_for_asset` (`selectors.py:1007`). Rendered at `AssetDetailPage.tsx:1370`. `2.237.9` |
| **AST-B-22** | The Overview header carries what the asset needs done | 08 | Nothing. Every field is on the wire | **ALREADY DONE** | `assetAttention()` and `AttentionStrip` (`AssetDetailPage.tsx:728-822`), mounted at `:483` between the status pill and the place line, with the raise control beside the overdue register only — an expired warranty carries none, *"because there is nothing to do about it"*. Silence on a healthy asset is deliberate and tested (`AssetOverviewPanels.dom.test.tsx:330`, *"its SILENCE is the feature"*). ⚠ The spec's **five served fields are four**: `asset_dict()["next_test"]` and `lifecycle.certification_due` are the same call under two names. `2.237.9` |
| **AST-B-23** | The three lists inside an asset use the shared table and its toolkit | 09, 11, 12 | Nothing. `DataTable` and the toolbar exist and are used by the registry | **NOT DONE** | Named open in the code twice: `AssetDetailPage.tsx:1629` (*"these three panels are hand-built tables (`DEF-MET-4968`, open: `AST-B-23` converts them)"*) and `:1684`. The panels are still `<table className={TABLE}>` with `ListPager` beneath and no search, filter, column selector or download. The Export tab's own filter runs over one page and the file says so out loud. ⚠ **Its stated blocker is gone** — step 1 recorded *"`AST-B-23` cannot be done before `AST-B-19`"*, and `AST-B-19` shipped at `2.237.8`. This is the largest buildable item on the list |
| **AST-B-24** | The reads table pages on the server | 09 | The same envelope `AST-B-19` asks for; this is its front half | **ALREADY DONE** | `asset_reads` (`api.py:266-282`) pages `selectors.asset_read_dates_page()` and shapes with `asset_reads_on()`. ⚠ **The page is fifty read DATES, not fifty rows**, and that is deliberate and stated in the endpoint: `BR-AST-029`'s typed pair folds into one row per date, so paging rows would cut a reading event across a page boundary. `count` is therefore a date count and a page's length varies with the register count. `2.237.8` |
| **AST-B-25** | Each Overview pencil opens a dialog that edits only its own panel | 16, 17, 18, 19, 20, 21 | Nothing on the server. `PATCH /assets/{id}` validates a partial payload already | **ALREADY DONE** | `AssetPanelEdits.tsx` (855 lines) — five dialogs plus the Measurement confirm second step. The pencil is declared once (`AssetDetailPage.tsx:823`) and the dialog mounted once (`:630`), one panel open at a time (`:339`). The server needed nothing: `_validate_asset(data, partial=True, current=asset)` already accepted 39 field names, already audited before and after, already refused a retired asset. All five `BILLING_AFFECTING_FIELDS` sit in the Measurement panel so **one** form carries the warning and **one** confirmation covers it. `2.237.9` |
| **AST-B-26** | A helper line is eight words or fewer | 14, 16–21, 22–27, 28–32 | Nothing. It is copy | **NOT DONE** | Measured on `07-frontend/src/i18n/locales/en.json` at HEAD: **26 of 64** `assets.*` help/hint keys run over eight words. The worst is still **36 words** — `assets.form.sizeClassHelp` — which is the same figure the blueprint measured, unchanged. Others at 19: `assets.imports.empty.helper`, `assets.reassign.finalReadHelp`, `assets.retire.finalReadHelp`. (My count and the blueprint's *27 of 37* are different key sets — it counted the helpers rendered on the screens it walked, I counted every asset help/hint key in the catalogue — but the worst string is the same string and it has not moved) |
| **AST-B-27** | The columns an asset holds that nothing can write | 28, 29, 30, 31 and the edit dialogs | A decision about which belong on which step | **ALREADY DONE** | The decision was ruled: PO 2026-09-12, *"this is correct - build it"*, for the four words `rubs · sqft · equal · absorb`. `ALLOCATION_RULES` is declared **once** (`AssetPanelEdits.tsx:100`) and **imported** by the add wizard (`AssetAddWizard.tsx:84`, *"IMPORTED, NOT RE-DECLARED"* — the eleventh-service lesson applied). `allocation_share_pct` and `allocation_rule` now travel from **both** write doors (wizard `:452-459`, dialog `:479`). `DEPRECIATION_METHODS` is declared at `:104` for the same reason. `2.237.9` / `2.237.10` |
| **AST-B-28** | Save as draft saves a draft | 24, 25, 26, 28–32, 33 | *"Nothing new. `BR-SHL-048` already puts a half-finished wizard in `wizard_parks`, and five wizards run on it"* | **PARTLY DONE — and the remainder is BLOCKED** | **`Save & exit` is wired on both wizards** where neither passed an `exit` prop at all before: `AssetAddWizard.tsx:855-866` (returns to the registry) and `AssetRetireWizard.tsx:437-448` (returns to the asset, because that is where the clerk came from). Step 1 found the spec's premise wrong — there was no button to fix. `AssetWizardExit.dom.test.tsx:198` asserts the hold and **fires the day it expires**. ⚠ **Park / *Save as draft* is refused with its reason and is not built**, and the spec's *"waits on nothing new"* is **false**: (a) `wizard_parks.flow` is a database CHECK constraint (`ck_wizard_parks_flow`, `apps/tenancy/models.py:1825`) over five values that does not admit `add_asset` or `retire_asset` — **a migration**; (b) **screen 33 (Drafts) does not exist**, and a draft nothing lists is a write nobody can read |

### 1.1 What that buys the build plan

* **Buildable today, nothing in the way:** `AST-B-23` (three lists onto `DataTable` — its
  blocker `AST-B-19` shipped), `AST-B-26` (copy, 26 strings), the download half of
  `AST-B-11`, the Priority column of `AST-B-18`.
* **Needs a decision before a line is written:** `AST-B-15` (contradicts D9 — PO),
  `AST-B-06` (a kit-wide `<select>` decision, not an Assets one).
* **Needs a migration and a screen:** `AST-B-28`'s Park half.

---

## 2 · The rule violations — still true? and does anything check them?

**The document's count is two different numbers and the cover is a third.** §09's table
renders **12 rows**; §09's own closing sentence says *"four of the **eleven** above"*;
appendix G indexes **11** and closes *"**Eleven violations.** One is partly
machine-checkable and ten are not."* The row appendix G drops is the **description budget**
row — which is exactly the one remedy R6 answers. The cover's *12 rule violations* matches
the table. **All 12 are carried below.**

`R11` and `R12` are the document's own numbering for the two halves of **B14 rule 39**
(rule 39's own text warns that the PO's `R12` label collides with another register). `R11`
= the spacing scale; `R12` = the field anatomy.

| # | Rule | What breaks it (as drawn) | **Still true today?** | **Is any gate enforcing that rule?** |
|---|---|---|---|---|
| 1 | `BR-WRK-056` | Two of the rule's four named ways in do not exist; `AssetDetailPage.tsx` holds zero references to `raiseWorkOrderPath` | **NO LONGER TRUE.** Three call sites now (`AssetDetailPage.tsx:509`, `:817`, `:1965`); `DEF-MET-4965`, `2.237.6` | **No.** Nothing reads rendered output and no test asserts a control's *absence*. The fix brought its own tests (`AssetDetail.test.tsx:1234`) |
| 2 | `R12` (B14 39) | Ten of eighteen fields render label → helper → input; label-to-input 29px or 47px, not 5 | **NO LONGER TRUE.** All five help-bearing `FormModal` variants render label → input → helper; measured 5/6/20 on 29 fields at 1280 and 1440 | **Partly, and only the ORDER.** `components/fieldAnatomyOrder.dom.test.tsx` asserts DOM position in six kit sites — jsdom computes no layout, so **the 5/6/20 figures have no gate** and are readable only through `10-scripts/render-checks/cr092-lane3-field-anatomy.mjs`. B14 rule 39's own status cell says so |
| 3 | B14 **18** + the 6–8 word convention | Zero of six tab descriptions inside the budget; two render nothing at all | **PARTLY TRUE.** Four were cut (24→5, 18→6, 9→6, 23→5). Meters and Behind the meter still render nothing — **by ruling D9**, not by oversight | **No.** `G43` clause (b) is a **ratchet at 50** on `max-w-prose` — it checks the *width* cap and nothing about word count or whether a slot is filled at all |
| 4 | B14 **12 · 13 · 14 · 16** | None of the four, on any of the Lifecycle tab's three tables | **MOSTLY NO LONGER TRUE.** Rebuilt 2026-09-12 on the shared `DataTable`: toolbar, sort, column selector, pager, empty states. **The download is still absent** | **No — and the file names why it could not have been caught.** `G43` holds the toolbar contract for lists that *declare* `searchFields` through `TableConfig`; a hand-built table declares none, so it *"sat outside the gate by construction. A check that reports zero over a scope it silently excludes"* |
| 5 | B14 **15** | 5 controls in one cell on every installed row, 3 on every inventory row, no overflow anywhere | **STILL TRUE.** `AssetRegistryPage.tsx:663-728` declares **six** `RowAction`s in one `RowActions` cell and no `RowActionsMore` | **Partly.** `G37` enforces three of four clauses — a row-actions cell contains only row actions, every element writes `aria-label`, no `<svg>` outside `icons.tsx` — **and not the cap.** `RowActionsMore` exists and one screen in the product uses it. Owned by `CR-093-BRC01`, sequenced after this pass releases the file |
| 6 | B14 **7** | Native date inputs everywhere; **Today shortcut nowhere**; no `min`/`max` on any of five, including one whose own help states a bound | **HALF TRUE.** The bounds landed — `AssetFlowPages.tsx:414` (`min`), `:708` (`max`), `AssetRetireWizard.tsx:304` (`min={asset.install_date}`) through `DatePickerField`'s new `min`/`max` (`FormModal.tsx:780-781`). **The Today shortcut is still nowhere** and is deliberately unbuilt | **Partly.** B14 rule 7's status cell now reads PARTIAL: `AssetLifecycle.test.tsx` asserts the log-repair bound, *including on a page mounted without the `today` prop*. The other four inputs are person-checked. No gate reads rendered output |
| 7 | B14 **31** | For a Billing Clerk the technician picker degrades to a bare text box holding a UUID — the one role the screen was written for | **NO LONGER TRUE.** `AssetFlowPages.tsx:604-617` reads `GET /work/crew-directory`; the field stays a list, and when the list cannot load it is shown greyed with a short line rather than turning into a text box | **Partly, and not for this shape.** `G28` scans catalogues (0), backend strings (20, baseline 24) and `raise` sites (542, baseline 478 — red and rising). **A uuid-shaped VALUE in a field is the one thing `G28` cannot see**; the two render-checks that do read one cover `S30` and `S15` only |
| 8 | B14 **13** | Sorting toggles asc↔desc forever; there is no third, cleared state | **STILL TRUE, product-wide.** `DataTable.tsx:54-59 nextSortState` returns `dir === "asc" ? "desc" : "asc"` and nothing else | **No.** It is the shared table, so this is not an Assets defect. Owned by `CR-093-BRC01` |
| 9 | B14 **16** | No first-page and no last-page control — only `table.pager.prev` and `table.pager.next` exist in the catalogue | **STILL TRUE.** `DataTable.tsx:961`/`:972` and `ListPager.tsx:87`/`:96` carry prev and next and no more | **No.** Out of scope to the Assets pass by PO ruling 2026-09-12 and carried by `CR-093-BRC01` — *"four rows reaching 54 lists is not a risk to take inside an Assets pass"* |
| 10 | `BR-SHL-025` | `writeBlockedReason` is declared as a prop on both tabs and passed by the page — and **read nowhere** | **HALF TRUE, and the remaining half is a live dead control.** Lifecycle now reads it at `AssetLifecycleTab.tsx:330` (the wrench) and `:685` (Turn into work). ⚠ **`AssetInventoryTab.tsx` still declares `writeBlockedReason` at `:74` and reads it at zero sites**, while its one control — *Parts in Work →* (`:218-222`) — is an ungated `<Button>`. A read-only role sees a live navigation button there | **No — and the document is right about why.** *"`G13` asks whether an optional prop has a caller. It does. Nothing asks whether the component reads it."* That is still exactly the position on the Inventory half |
| 11 | `R11` / now **B14 40** | Two full-page wizards render 32px and the one screen that is not a wizard (Raise work order) renders the 40px wizard title | **NO LONGER TRUE.** `PageHeader.tsx:309-312` emits `text-h2` (32px) on **both** the `h1` and `h2` branches, so the size is independent of the heading level. `2.237.7` | **YES — and this one changed category.** **B14 rule 40 was ratified 2026-09-12, after the document was read**, and it is ENFORCED by two checks that cover different things: `components/PageHeader.test.tsx` asserts the component emits the class, and `10-scripts/render-checks/cr093-page-title-size.mjs` reads `getComputedStyle` against the **built** stylesheet at 1280 and 1440, with a `--before` mode that must fail at 40px |
| 12 | `R11` (B14 39) | The shell's rail item at `9px 12px` with a 10px icon gap, and the status pill at `2px 9px` — two off-scale literals | **STILL TRUE, and deliberately.** `AppShell.css:103-104` and `StateFrame.css:60-63`, both now carrying `DEF-MET-4963` and the words *"MEASURED, DELIBERATELY NOT CHANGED"* | **No.** The CR-016 browser check measures type sizes and control heights, **not padding**. Recorded rather than tidied, which is the right outcome for a value that may be optically correct |

**Scoreboard.** Of the 12: **4 are no longer true** (1, 2, 7, 11) · **3 are half true**
(3, 6, 10) · **1 is mostly no longer true with a named remainder** (4) · **4 are still
true** (5, 8, 9, 12), and **three of those four are shared-component rows the PO moved to
`CR-093-BRC01`**. The genuinely-Assets survivor is **row 10's Inventory half**.

**And the column the table exists for has moved once.** At the time of the read, *"would
a machine have caught it?"* was **No** for eleven of twelve and *Partly* for one. Today
**row 11 is a Yes** — B14 rule 40 was ratified and given two checks a day after the
document was read. It is the only one, and it is the only row where a rendered-output
check now exists.

---

## 3 · B14's rule count — the document's number is wrong, and it was wrong the day it was written

The document states on p3 that B14 holds **"38 binding UI rules."** Do not take that
number, and `CLAUDE.md` says why: this count has been wrong six times.

**Counted from B14's own status tables, mechanically:**

```
rule numbers present: 1..21, 31..42
count: 33
gaps in 1..42: 22 23 24 25 26 27 28 29 30
```

**B14 holds THIRTY-THREE binding rules**, numbered **1–21 and 31–42**. Rules **22–29 were
never minted** — zero mentions in B14, zero citations anywhere — and **30 was declined**
on 2026-08-30 (the PO answered the instance, *"for estimate reads - keep it modal"*, and
in the same sentence said of rule 31 *"that is a rule"*; the number is left unused on
purpose so every existing citation of rule 31 still resolves).

⚠ **The document's 38 was not stale — it was never right, and it has become *less* wrong
by accident.** On 2026-09-10/11, when the document was read, B14 held rules 1–21 plus
31–38, which is **29**, rising to **30** when rule 39 was ratified on 2026-09-11. So the
figure was out by **eight or nine** on the day it was written. Three rules have since been
ratified — **40** (page-head title 32px, 2026-09-12), **41** (the product matches the
blueprint exactly, 2026-09-13) and **42** (a screen is built from the drawing *as an
image*, 2026-09-13) — which has narrowed the error to five without anybody correcting it.

**A lane that trusts 38 will go looking for rule 25 and find nothing.** Count B14's own
status table; never trust a number in a pointer, this file's included.

⚠ **One more stale claim in §09, and it is one `CLAUDE.md` names by defect id.** The
*"Rules these screens are exempt from"* block (p138) says of rule 21: *"A utility written
in a file **not** on that list renders as nothing at all while `tsc` and every `toContain`
assertion pass."* **That mechanism is wrong** and was corrected by PO ruling on 2026-09-12
(`DEF-GOV-5102`, verbatim *"Yes correct it"*). `styles/tailwind.css` imports the utilities
with `source(none)` and then declares `@source "../"`, so the compiler scans the whole of
`src/` and emits a utility for **any** file. The real consequence of a utility in an
unlisted file is a **red `G31` at merge**, and the fix is to add the file to the ledger —
never to reach for a stylesheet class, which is what rule 21 forbids. The exemption's
*conclusion* is still correct (all fourteen asset feature files are listed, so the trap
does not apply here); its *reasoning* would send the next lane the wrong way.

---

## 4 · The six remedies, their subjects and their carry-over arithmetic

Read off pages 139–152 as images. **Two page-map corrections first**, because the index
made this session (`blueprint/00-index.md`) is wrong about them and it is a derived index:

| | `00-index.md` says | **The PDF says** |
|---|---|---|
| **R3** | *"Asset # helper moves below its input", pp. 144–145* | **"The service field offers the list it already has" (`AST-B-03`), Figure 53, pp. 143–145.** The Asset # helper move is element **1** of R3's legend, not R3's subject |
| **R2** | pp. 142–143 | Figure 52 opens on **p141** and runs to p143 |
| **R4** | p146 | Figure 54 opens on **p145** and runs to p147 |
| **R6** | p151 | Figure 56 opens on **p150** and runs to p152 |

R1 and R5 match the index.

| Remedy | Subject | Spec | Screens changed | **Carry-over arithmetic, as printed** |
|---|---|---|---|---|
| **R1** | The asset gets the two doors its own rule already names | `AST-B-02` | 08, 12 (fig. 51) | as-built **9** · unchanged 9 · moved 0 · relabelled 0 · **removed 0** → remedy **11** = 9 − 0 + 2 new ✓ |
| **R2** | The registry's numbers become numbers | `AST-B-01` (+ rules 13, 15, 16 riding along) | 01 (fig. 52) | as-built **28** · unchanged 22 · **moved 6** (four row actions into the overflow, both kept reachable) · relabelled 0 · **removed 0** → remedy **30** = 28 − 0 + 2 new ✓ |
| **R3** | The service field offers the list it already has | `AST-B-03` | 28 (fig. 53) | as-built fields **9** · unchanged 6 · moved 1 (the Asset # helper) · changed 1 (bare text → searchable picker) · relabelled 1 (the help sentence) · **removed 0** → remedy **9** = 9 − 0 + 0 new ✓ |
| **R4** | Every helper moves under its own input | `AST-B-13` | 14, 16–21, 23 (fig. 54) | as-built fields **18** · unchanged 8 (the eight with no helper, already at 5px) · **moved 10** (the helper's position, on every field that has one) · relabelled 0 · **removed 0** → remedy **18** = 18 − 0 + 0 new ✓ *(the two NEW rows are control affordances, not fields)* |
| **R5** | The opening read becomes a field a person can fill in | `AST-B-14` | 29 (figs. 55) | as-built fields **9** · unchanged 8 · changed 1 (disabled → enabled) · relabelled 1 (the same field, counted once) · moved 0 · **removed 0** → remedy **11** = 9 − 0 + 2 new ✓ |
| **R6** | One description per screen, six to eight words | `AST-B-15` | 01–06 (fig. 56) | descriptions today **4 rendered + 2 dead strings = 6** · inside 6–8 words **0** · relabelled 4 · new 2 · **removed 0** → after **6** = 4 relabelled + 2 new, all six inside 6–8 words ✓ |

**Two governing rules stated on p139, and both hold across all six:**

* *"A remedy never loses anything."* Every field and every piece of information
  architecture on the as-built drawing survives — grouping, order, tabs, hierarchy, words
  — *"unless somebody has ruled that it goes and the ruling is quoted."*
* Screens **05a–05c** and **screen 18** are whole screens rather than changes to one, so
  they are drawn as numbered remedies **in §02**, beside the as-built they replace.

**One divergence between R2 as drawn and R2 as built, worth a row.** R2's legend reads
*"KPI figures · a new aggregate read over the **whole filtered set**, not the page."* What
shipped counts **the tab's whole population, deliberately NOT narrowed by `q` or by the
caller's filters** — and `asset_kpis`'s docstring argues the case: *"The client only ever
showed these figures when there was NO search and NO filter, so the tab's own population
IS what the cards have always meant … Narrowing them with the filter would make* In
inventory *and* Meters in service *mutually exclusive and at most one card non-zero, which
is not a strip anybody drew."* Under B14 rule 41 that is a drawn element disagreeing with
the built one, and it should be either ratified or corrected rather than left as two
descriptions of one strip.

---

## 5 · Appendix K — **the document says one thing is removed. It is two.**

You asked me to verify the claim that exactly one thing is dropped across all six
remedies. **It is false, and the document contradicts itself on the point.**

**What p139 says** (and what `00-index.md` repeats): *"Across all six remedies in this
document, **exactly one thing is removed** — the dialog frame on screen 18, under a quoted
instruction, and it is a container rather than a field. **Appendix K carries that one row
and nothing else.**"*

**What appendix K itself carries** (p209, read as an image, and p210's own summary line
directly beneath it):

| Screen | What is dropped | Disposition | The ruling, quoted | What it costs the person who used it |
|---|---|---|---|---|
| **07** | The **dialog frame** around the edit form | REMOVED | Instruction, 2026-09-11: *"this should be form and not modal."* | **Nothing.** A container, not a field: all nine fields, the forward-only note and both buttons carry over. What is lost is the dimmed backdrop; what is gained is an address to return to and a second door from the asset |
| **05c** | The **Asset value panel** — *Buy value $3,381.00*, *Present value $2,608.02*, and its line *"Computed from each device's recorded purchase cost and straight-line age. Nothing here posts anywhere."* | REMOVED | Instruction, 2026-09-11: *"remove this - Asset value"*, quoting the panel in full | **Two figures computed nowhere else in the product.** Buy value and present value across the whole tenant appear on this panel and on no other screen, so a person who used them loses them entirely |

p210, immediately under the table: **"Two rows, and both carry a quoted ruling. Rows with
no quoted ruling: 0."**

**So the count is two, appendix K is the correct half, and the summary on p139 is the
stale half.** The difference matters: row two is a **field-bearing** removal with a stated
cost, and the sentence that says *exactly one thing is removed* is the sentence a reader
uses to decide they need not check.

**Both removals have shipped.**

* The dialog frame — `AssetEditPage.tsx` is the form with its `FormModal` frame removed
  and no second copy anywhere; the file says so in its own words. `2.239.9`.
* The Asset value panel — `AssetLifecycleTab.tsx:44-56`: *"ITS RULED REPLACEMENT, THE
  'Asset value' PANEL, IS NOW GONE TOO — PO INSTRUCTION, 2026-09-11 … It is the ONE
  field-bearing removal in the whole `CR-092` blueprint and it has a stated cost … The
  server still serves `asset_value`; nothing renders it."* `2.237.5`.

⚠ **A consequence nobody has ruled on:** `lifecycle_view` still computes and serves
`asset_value` (`selectors.py`, the `return` block) and **no screen reads it**. That is a
served fact with no reader — hard-won law 2's own shape — left behind by a removal that
was otherwise done exactly right. Either the selector should stop computing it or the
absence should be recorded; today it is neither.

⚠ **One more thing appendix K is right about that p139 glosses.** The closest thing to a
third removal is **R2's four row actions moving into an overflow menu**, graded MOVED on
purpose — *"a control behind a `…` is still reachable and B14 rule 15 asks for exactly
that arrangement"* — and appendix K records it *"so a reader who believes demoting a
control into an overflow **is** a removal for everyone who never opens overflow menus can
argue the point — and they would not be wrong to."* That is the register behaving
correctly and it should survive into any build plan.

### Screen numbering — the document uses two systems and does not say so

Appendix K calls the edit form **screen 07**; p139 calls the same thing **screen 18**.
§08, §09 and appendix G number the raise-work-order finding **screens 10, 14** where §12
numbers the same specification **screens 12, 27**; §08 puts *"Your role can't list
users"* on **screen 21** where §12 puts `AST-B-04` on **screen 23**. **The later sections
(§12 and the index) use one numbering and the earlier ones (§08, §09, appendix G,
appendix K) use another**, and no section states the mapping. Every screen reference in
this file is quoted from the section it was read in and is labelled accordingly — **do
not cross-reference a screen number between §08/§09/K and §12 without checking the
picture.**

---

## 6 · The 49 stated absences

Totals verified against the document's own arithmetic on p135: **A 17 + B 13 + C 11 + D 1
= 42, plus E 7 = 49**, of which **7 carry a specification** and **42 are out of scope with
a reason and a ruler named**.

⚠ **Two internal miscounts in this section.** §08-B's heading reads **"(13)"** and its
own opening paragraph reads *"All **fourteen** are OUT OF SCOPE"*; the table renders 13
rows and p135's total uses 13. And §08-C's own note admits the class was *"a paragraph
until this pass, which is why they were never rows: a list of eleven things inside a
sentence cannot be counted by anyone checking the total, **and the total was indeed
wrong**."*

### A · Things a person is told cannot be done (17) — p129–131

| # | What is absent | Decision in the doc | **Today** |
|---|---|---|---|
| A1 | Raising a work order from the asset itself (no copy — the controls are simply not there) | `AST-B-02` | **NO LONGER TRUE** — three controls, `2.237.6` |
| A2 | Searching, sorting, filtering or paging anything on the Lifecycle tab (no copy — no toolbar exists) | `AST-B-11` | **NO LONGER TRUE for the toolkit** (rebuilt on `DataTable`); **STILL TRUE for the download** |
| A3 | *"Your role can't list users, so enter the technician's ID."* | `AST-B-04` | **NO LONGER TRUE** — the string and the degradation are both gone, `2.237.4` |
| A4 | The **Service** field has no option list | `AST-B-03` | **NO LONGER TRUE** — a `SelectField` over `GET /settings/services`, `2.237.3` |
| A5 | No KPI figure on the three list tabs | `AST-B-01` | **NO LONGER TRUE** on the two tabs that draw a grid; Sub-meters draws no strip at all |
| A6 | *"No template applies to this kind of asset."* — the submit stays disabled | `AST-B-10` | **STILL TRUE as a state, and that is now correct.** The dead end gained a second sentence, a `title` and an `aria-describedby`; the refusal is the honest answer |
| A7 | ~~*"An opening read is recorded through Meter Reads once the meter is installed — it cannot be captured here."*~~ | `AST-B-14` — **WAS out of scope, NOW a specification** | **NO LONGER TRUE** — the string is gone and the field is enabled, `2.237.10`. The doc keeps the superseded seam reasoning on purpose, *"because the seam argument was real and was overruled"* |
| A8 | Yard / On-vans split · *Reorder at* column · **Raise reorder** · stock-count import | OUT OF SCOPE — PO 2026-08-22 §10-D5, *"Launch with counts & costs only."* | **STILL TRUE** — `AssetInventoryTab.tsx` draws the strip *"MINUS the two D5 cut cards"* and the tests assert each absence by name |
| A9 | The *Cost to Finance* panel, the depreciation figure and *"Posts to 5300 O&M and 5400 Depreciation"* | OUT OF SCOPE — PO 2026-08-22 §10-D3 (no depreciation engine; only the ledger posting service writes journal lines, hard rule 5) | **STILL TRUE** — and its ruled replacement has since been removed too (appendix K row 2) |
| A10 | *"The amount and your choice are recorded on the asset. Nothing is posted to the ledger."* | OUT OF SCOPE — same ruling | **STILL TRUE** — and consistent with B14 rule 34's pair (§11 checks it) |
| A11 | Tariffs and credited dollars anywhere on the behind-the-meter tab | OUT OF SCOPE — `BR-AST-025`, D2 2026-08-22 | **STILL TRUE** |
| A12 | r10's `WO-####` lines in the map popup | OUT OF SCOPE — §10-D7, *omitted rather than faked* | **STILL TRUE** — and now arguably reviewable: the fact exists since `CR-070` |
| A13 | Demand flag · read route · read sequence · warranty *term* select | OUT OF SCOPE — lane instruction: no column exists, nothing renders, each reported | **STILL TRUE** — `AssetAddWizard.tsx`'s trailer still carries all four as E3/E4 exceptions |
| A14 | *"Bulk assignment moves inventory to units only. A unit-to-unit move goes one at a time, or by file import."* | OUT OF SCOPE — `BR-AST-036/038` | **STILL TRUE** |
| A15 | *"Maintenance entries are never edited or deleted — a correction is a new entry."* | OUT OF SCOPE — `BR-AST-018`, append-only by rule | **STILL TRUE** |
| A16 | *"This cannot be undone. Retired is the end state — there is no un-retire."* | OUT OF SCOPE — `BR-AST-030`, terminal by rule | **STILL TRUE** |
| A17 | *"Background map is switched off."* · *"Assets are open to System Admins and Billing Clerks."* | OUT OF SCOPE — a tenant configuration and a role rule, both server-enforced | **STILL TRUE** |

### B · Server refusals a person can meet (13) — p131–132

Every one is a `message_key` raised by `apps/assets` and rendered through the shared
refusal path, and **all thirteen are OUT OF SCOPE — each is a rule doing its job and each
names either the remedy or the screen that holds it.** **All thirteen are STILL TRUE and
should stay that way.** For the record, with the rule each rests on:

`BR-AST-013` (history blocks a delete — *"Retire it instead"*) · the same rule's other
branch (only inventory deletes) · `BR-AST-030` (retired is the end state) · `BR-AST-020`
(legal transitions from the behaviour class) · the same, on assignment · `BR-AST-022` (the
read and the move are one transaction) · the same rule's precondition (a final read needs
a current assignment) · `BR-MET-003` (an unenabled service, naming **Settings**) ·
`BR-AST-043/044` (three refusals naming **Reference data**) · `BR-AST-031` (a missing
lifecycle stage) · `BR-AST-047` (no purchase cost or expected life, so no book value) ·
`BR-AST-021` (the replacement is itself retired / not found) · `BR-AST-049` (no numbering
series — **degrading rather than blocking**).

⚠ The one worth re-reading is the last: it is the only refusal in the set that lets the
person carry on. That posture is what `AST-B-10` asked the raise form to adopt, and now has.

### C · Honest empties (11) — p132–133

All eleven are OUT OF SCOPE — an empty state that says what creates content **is B14 rule
17 working**, and there is nothing to specify. **All eleven are STILL TRUE.** Meters ·
Sub-meters · Behind the meter · Inventory · Map (no coordinates) · Map (no match for the
filter) · Certifications & tests (none due) · Warranty & supplier (none recorded) · Reads
(none taken) · Export (no file yet) · Maintenance (no history).

Two notes:

* **Map, no coordinates** is the one the document says to read twice, because it names the
  cause rather than the symptom: *"Premises gain coordinates from the geocoding run; until
  then the map has no markers to draw."*
* **Export, no file yet** was honest about the queue while *"the file it promises does not
  arrive"* — the live defect beside it, `AST-B-20`. **That half is now fixed**; the empty
  state itself was always correct.

⚠ **And one absence the product SHOWS and never STATES, which the document files as a
description rather than a specification** (p133): `AssetDash` renders a bare italic `—`
with no title and no accessible text (`assetsShared.tsx:202-204`), used for every unserved
KPI and every empty column cell in this module. On screen 01 that means **loading**,
**genuinely none** and **we cannot compute this from one page** are the same picture.
**STILL TRUE** — `AssetDash` is unchanged and is used at eight sites in `AssetDetailPage.tsx`
alone. Nobody has ruled on it and fixing it is a shared-component decision.

### D · Copy that reaches nobody (1) — p133

| Key | String | **Today** |
|---|---|---|
| `assets.sub` | *"Every meter, sub-meter and behind-the-meter device that can affect a bill."* | **STILL TRUE.** Present in **11 of 11** catalogues, **zero render sites**. The only occurrences outside the catalogues are a code comment (`AssetRegistryPage.tsx:1270`) and this register. Orphaned when the shared page-header conversion dropped the kicker/sub pair |

⚠ **And the class has grown by two since the document was written**, both created by fixes
that were otherwise correct:
`assets.explainer.meters` and `assets.explainer.behind_the_meter` are in **11 of 11**
catalogues and reach no screen, because `AssetRegistryPage.tsx:812` passes an explainer
only for `sub_meters` under ruling D9. So **group D is three, not one**, on today's code.

### E · Absences found after the register was first written (7) — p134–135

Four of the seven are **drop-down sources**, and the document makes the point that none
could have been seen in a drawing — *"a picker that offers the wrong list looks exactly
like one that offers the right list."*

| # | What is absent | Decision | **Today** |
|---|---|---|---|
| E1 | Connection size is not filtered by service | OUT OF SCOPE — ruled and filed already (`DEF-3300`); dropping a size already held would silently change what the form saves | **STILL TRUE, and correctly so** |
| E2 | The premises and unit pickers stop at 500 rows | `AST-B-19` — a hard cap on a picker is the shape `NFR-5` exists to forbid; folds into the pagination specification | **NEEDS A RULING.** `AST-B-19` shipped for the three *in-asset* lists; **the pickers were not in its scope** and nothing I read changes them. It is a live `NFR-5` exposure at T5 and it should not stay folded into a closed row |
| E3 | Test cadence cannot be a regulator's interval (`CADENCE_MONTHS` frozen at 12 · 24 · 60) | `AST-B-27` — the column takes any integer, only the list is short | **STILL TRUE.** `AssetAddWizard.tsx`'s help still reads *"Left blank, the asset type's own default applies — backflow preventers 12 months, meters 96"*; nothing widened the list. A tenant whose backflow rule says 36 months still cannot express it |
| E4 | Depreciation method has no list anywhere | `AST-B-27` — inside the columns-with-a-reader-and-no-writer specification | **NO LONGER TRUE.** `DEPRECIATION_METHODS = ["straight_line", "none"]` is declared at `AssetPanelEdits.tsx:104` and offered on the Cost & value dialog |
| E5 | Unit of measure is typed, not picked | `AST-B-03` — the tenant's units ride the same `GET /settings/services` payload | **STILL TRUE.** `AssetAddWizard.tsx` step 2 renders *Unit of measure* as a text input (`kgal`), and the helper still reads *"Explicit, always — kWh, kgal, ccf and so on."* `AST-B-03` fixed the **Service** field and not this one |
| E6 | A draft never expires and nothing limits how many there are | OUT OF SCOPE — ruled and deliberately left open, `BR-SHL-047`: *"a wizard that refused to park after N days would be enforcing a rule nobody made."* ⚠ *"It is not free here: a forgotten* retire *draft means a decommissioned meter goes on billing"* | **MOOT TODAY and it will return.** No asset wizard can park at all (`AST-B-28`'s blocked half), so there are no asset drafts to expire. **The day the `wizard_parks.flow` migration lands, this row becomes live**, and the retire-draft consequence above is the reason it should be read before that migration is written rather than after |
| E7 | Read methods are served by two endpoints | OUT OF SCOPE — ruled: `GET /reads/read-methods` was minted because `/lookups/{code}` was System-Admin-only (`DEF-196`); that gate has since widened to *read by any role*, so the duplication is redundant rather than load-bearing. **Removing it is metering's call, not this document's** | **STILL TRUE.** `apps/assets/lookups.py:255-266` records the same widening from the other side. Redundant, harmless, and still two |

**Recount, honestly:** of the 49, **7 are no longer true** (A1, A3, A4, A5, A7, and the
toolkit half of A2, plus E4), **1 is moot but will return** (E6), **1 needs a ruling it
does not have** (E2), and **the rest stand** — as they should, because 42 of them are
rules doing their job or rulings being honoured.

---

## 7 · ⚠ A live defect found while checking this, which the document does not contain

**Nothing in §08–§12 predicts it, and it is the mirror of the fix it rode in on.**

`GET /assets/lifecycle` **gained server-side windowing** — `asset_lifecycle`
(`api.py`) now reads `parse_list_params` and passes `page`/`per` into
`selectors.lifecycle_view(page=…, per=…)`, which windows the certifications list
(`WINDOW_DEFAULT_PER = 50`) and returns a **`certifications_window`** key beside it. The
selector's own comment explains the split deliberately: certifications is *"the ONE list
here that grows with the ESTATE"*; warranty groups and the age forecast are
catalogue-shaped and are served whole on purpose.

**The front end never asks for it, and never reads what comes back.**

* `getAssetLifecycle(client)` (`endpoints.ts:9034-9036`) takes no options and calls
  `/assets/lifecycle` bare.
* `AssetLifecycleTab.tsx:258-260` queries it with a **constant key** (`["assets",
  "lifecycle"]`) — no page in the key.
* All three tables then page **in the browser**: `clientPage(data.certifications, …)` at
  `:483`, and `clientPage` returns `total: out.length` (`:224`).
* **`certifications_window` is read by nothing.** `grep -n "certifications_window"
  07-frontend/src/api/endpoints.ts 07-frontend/src/features/assets/AssetLifecycleTab.tsx`
  returns nothing at all.

**What a clerk sees.** On a tenant with more than 50 certifications due, the
Certifications & tests due tab shows the **first fifty** and its pager reads *"Showing
1–50 of 50"* — no next page, nothing that says anything is missing. It is the weekly list
a utility opens, silently truncated, on a screen that was rebuilt precisely to stop being
the one list in the module without a pager.

**Every check passes over it**, which is why it needs writing down: `tsc` passes (the
extra key is simply unread), the suites pass (their fixtures hold fewer than fifty rows),
and `DEF-MET-4962`'s register row reads as closed on the endpoint it names.

⚠ **The tab's own header comment is now half stale and says the opposite:** *"The three
tables page, sort, search and filter **in the browser** over the whole `GET
/assets/lifecycle` payload, **which takes no page parameter at all**."* That was true when
it was written; the endpoint takes one now, and the sentence is what would stop the next
lane looking.

**No id is allocated here** — `CLAUDE.md` law 11 and this lane's instructions put
allocation with the coordinator. **Please allocate a `DEF-MET-` row for it**; it is a
`built-not-wired` escape and the fix is three lines plus the key in the query.

---

## 8 · The cross-module surface — §11 and appendix H

**The one thing to know before reading the rest** (p153, and it is still true): the assets
tables live in **`06-backend/apps/assets/`, a Django app of its own** — *not* in
`apps/metering`, where `CLAUDE.md`'s module map puts them (*"metering … owns assets per B2
r4"*). Every `/assets*` route is declared in `apps/assets/api.py`; `apps/metering` mounts
exactly one, the usage strip (`assets/<uuid:asset_id>/usage`, `metering/api.py:2976`).
**This is not a breach and it is not new** — the module's own docstring flags it as an *Eng
hosting disposition* — but **`CLAUDE.md` has never absorbed it**, so a lane reading the
module map alone goes looking in the wrong directory. Recorded as a description; nobody
has ruled that the map should change.

### 8.1 Does the handoff land? (§11 ¶1, p153–154)

| From → To | The shared fact | Verdict (doc) | **Today** |
|---|---|---|---|
| assets → metering | A unit's identity and its premises, for every *Assigned to* cell, address and map pin | **Lands** via `seams.unit_ref()`, returns a dict | **HOLDS** |
| assets → metering | The final read, captured atomically with a move | **Lands, and refuses correctly** — metering commits in the caller's transaction and hands back its dict; the closing assignment takes `final_read_id`; a failure refuses the move rather than half-doing it | **HOLDS — and it is now a precedent, not just a seam.** `capture_opening_read` was built to the same shape for `AST-B-14`, which is exactly the argument R5's card made |
| assets → customers | The active account on the unit — the live billing chain | **Lands.** Was unwired while customers owned no tables; the account leg is served now and screen 08 draws it | **HOLDS** |
| assets → billing | Whether an invoice line references this asset, for the delete gate | **Lands.** A probe, re-run by the server at delete time rather than trusting the action set it served | **HOLDS** |
| assets → work | `work_orders.asset_id` — read for the Maintenance panel's Work-order column, written by Work's own endpoint | **Lands one way and not the other.** *"The read works. The write is reachable from five places, and two of the four `BR-WRK-056` names — both on the asset's own screen — do not exist. This is the module's largest finding and it is a cross-module one: the rule is Work's, the missing controls are on an Assets screen, and neither owner's tests cover the join"* | **NO LONGER TRUE — this was the module's largest finding and it is closed.** Both controls exist (`AST-B-02`), and `apps/work/asset_door.py` states the design that keeps the boundary: *"`apps/assets/**` gains no line of code at all — which is a stronger statement than 'assets writes nothing to `work_orders`', and it is the one a grep test can prove"* |
| assets → integrations | The basemap tile host, from the page policy | **Lands**, and worth naming rather than leaving implicit: every pan on screen 06 sends the viewport around a tenant's asset locations to whichever host that row names. On the shipped default that is Esri, and the egress was **accepted by ruling (§10-D6)** rather than overlooked | **HOLDS, and the ruling stands.** Worth re-reading at onboarding, not re-deciding |
| assets → identity | The technician list for screen 23 | **Does not land for the role that needs it.** `GET /users` is System-Admin-only; `BR-AST-038` lets a Billing Clerk log a repair. *"The seam is fine — the permission on the far side makes it unusable for half its callers"* | **NO LONGER TRUE.** The door moved to `GET /work/crew-directory`, and `GET /users` was **not** widened — which is the right shape: the seam was never the problem |
| assets → tenancy | The asset number series, and the export kernel | **Lands.** A meter number is allocated from the tenant's series and never taken from an uploaded file (`BR-AST-049`) | **HOLDS** |

### 8.2 Does any module write another's tables? — **checked here, not taken on trust**

`CLAUDE.md` forbids a cross-module write outright, so I re-ran the search rather than
quoting the document's answer.

```
grep -rnE '\.objects\.create|\.save\(\)|\.objects\.update|\.delete\(\)' 06-backend/apps/assets/*.py
```

Six hits, and **every one writes an `apps.assets.models` table**: `lookups.py:160`/`:186`
(`AssetType`, `AssetLifecycleStage`, `MeterType`, `ReadMethod` — declared at `:193`,
`:204`, `:222`, `:245`), `services.py:492` (the same four via `flat_model`), `:1414` and
`sample_data.py:1126` (`Asset`). **Zero foreign writes. The rule holds.**

Two places it could plausibly have gone wrong and did not:

* A service point on a unit goes through `metering.services.ensure_service_point()`, so
  **metering creates its own row**.
* The Raise-work-order screen lives under `features/assets/` in the front end and posts to
  `POST /work-orders` — **Work's own door.** `apps/assets` gains not one line of code for
  that feature, and a test asserts it by name.

### 8.3 Every seam, graded (appendix H, p155–156)

**Eight crossings — six HEALTHY, two LEAKY by the letter, nothing leaking today, zero
WRITING, zero ABSENT.** Re-checked at HEAD:

| From → To | The file that crosses | Grade | **Today** |
|---|---|---|---|
| assets → metering | `seams.unit_ref` · `service_point_ref` · `latest_read_for_asset` · `typed_reads_for_asset` · `enabled_service_codes` · `capture_final_read` · `read_count_for_asset` · `tenant_today` · `export_rollup_last_month` | HEALTHY (dicts, sets, ints, dates) | **HOLDS** — and `capture_opening_read` joins the list as a ninth, same shape |
| assets → metering | `seams.unit_row` | **LEAKY by the letter** — returns a **model instance**, not a dict | **STILL TRUE and still leaking nothing.** `seams.py:98 def unit_row(unit_id) -> Any`; three callers (`services.py:1118`, `:1275`, `:1927`) all **discard the return** and use it purely as a same-tenant existence probe. *"The day a fourth keeps it, the boundary is gone and nothing will say so"* — and that is still the position: no check exists |
| assets → customers | `seams.active_account_for_unit` | HEALTHY (`dict \| None`) | **HOLDS** |
| assets → billing | `seams.invoice_line_count_for_asset` | HEALTHY (`int`) | **HOLDS** |
| assets → identity | `seams.actor_display_names` | HEALTHY — `dict[id, name]`, *"names, never ids, which is what keeps B14 rule 31 true on screen 12"* | **HOLDS** |
| assets → tenancy | `exports.py:41-42`, `lookups.py:261` | **LEAKY by the letter** — direct imports that bypass `seams.py` | **STILL TRUE.** `exports.py` imports `apps.tenancy.exports` (the export kernel and `ExportColumn`/`ExportResource`) and `lookups.py:261` imports `apps.tenancy.services`. Named so it stays a decision rather than an oversight: it is a shared export **kernel**, closer to framework than to data, and no row of another module's is read or written through it |
| assets → work | `features/work/workEndpoints.ts`, from a front-end file under `features/assets/` | HEALTHY — *"and deliberately so: the file lives under `features/assets/` because that is where a clerk is standing, not because assets owns the write"* | **HOLDS** |
| assets → integrations | `getPagePolicy()` in `AssetMapTab.tsx` | HEALTHY (a policy dict carrying `tile_host`) | **HOLDS** |

---

## 9 · Three things about the document itself that a build plan needs

1. **§12's closing paragraph is stale and contradicts its own table.** p161 reads *"**Twelve
   live specifications.** Two — `AST-B-10` and part of `AST-B-04` — wait on a decision or a
   new read; the other ten wait on nothing at all."* The table above it carries **24 live
   rows** and the cover says 24. Twelve is a figure from an earlier version of the pass.
   The *shape* of the sentence survives the correction and is the better half of it:
   **this module is not short of capability, it is short of the last connection between
   capability and screen** — which is why seventeen of the twenty-four could be closed in
   twenty-seven versions.
2. **Three "waits on nothing" claims were wrong, in both directions.** `AST-B-18` said
   *nothing on the server* and priority was genuinely unserved at the time (it is served
   now); `AST-B-28` said *nothing new* and Park needs a **migration** plus a screen;
   `AST-B-14` says *nothing* in §12 and *a create-time read seam* on R5's card — the card
   was right and the seam had to be written. **Check the claim against the route table
   before agreeing with it**; `grep 'path(' 06-backend/apps/*/api.py` answers it in one
   command, and `/assets/{id}/work-orders` turns out to live in `apps/work/api.py:1681`
   rather than where a reader would look.
3. **The document cites an appendix that does not exist.** p210's *Completeness, scoped*
   box reads *"every field in **I**"* — and the appendix list runs A–L **with no I**
   (fields are in **C**, drop-downs in **L**). A small thing, but it is the same class as
   the rule count: a pointer nobody re-checked.

## 10 · One finding outside this lane's scope, reported because law 7 says to read the reds you did not cause

**`CHANGELOG.md:1583` is a bare `=======` — an unresolved merge-conflict marker committed
into the changelog.** There is no matching `<<<<<<<` or `>>>>>>>`; it sits between the
`2.237.5` and `2.237.4` entries. Confirmed present in `HEAD` (`git show HEAD:CHANGELOG.md
| grep -n '^=======$'` → one hit), and `git log -S"=======" -- CHANGELOG.md` dates it to
**`cf45a3d2`, 2026-09-13** (*"Communication dialog: start from the utility's own wording…"*)
— **not this lane's, not the Assets pass's, and pre-existing at the commit this audit
started from.** Nothing in the repo reads the changelog, so nothing will ever go red on it.

---

## Trace

* **Read as images at scale 4**, per B14 rule 42: pages **128–161**, **194–195**,
  **209–210** of `05-prototype/01 Assets Menu Blueprint.pdf`. No claim in this file comes
  from the text layer, from
  `04-docs/05-modules/05-assets/wireframes/CR-092-assets-screens.html`, or from
  `04-docs/05-modules/05-assets/08-screen-layouts.md` — the last two are derived copies and
  were not opened (PO, 2026-09-13).
* **Corrections made to `blueprint/00-index.md`'s remedy table after re-reading the
  pictures:** R3's subject (it is the service field, `AST-B-03` — not the Asset # helper,
  which is element 1 of R3's legend), and the page ranges of R2 (141–143), R4 (145–147)
  and R6 (150–152). The index's R1 and R5 rows are right.
* **Verified against code at `2.261.3`, HEAD `11307c79`** (`check_head_current.sh`: *PASS —
  HEAD is the tip of `origin/claude/eager-johnson-r0k88b`*). Every verdict names the file
  and line read.
* **B14 counted from its own status tables**, mechanically: 33 rules, 1–21 and 31–42.
* **No product code changed. No register edited. No id allocated.** One file written.
