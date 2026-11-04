# CR-092-BRC01 · step 2 · lane 1 — THE ASSETS REGISTRY, FIXED

**The fix pass for the ten rows step 1 filed.** Screens **01 Meters · 02
Sub-meters · 03 Behind the meter · 04 Inventory · 05a/05b/05c Lifecycle ·
06 Map**.

**Built at** `ce623f444`, the tip this lane started from. **Version `2.237.5`.**
**Measured on `pine-hill` (135 assets, 110 meters)** unless a finding says
otherwise — `brazosbend` holds 14 and cannot reproduce anything about page two.

| row | what it was | what it is | status |
|---|---|---|---|
| `DEF-MET-4953` | four KPI cards render four em-dashes | **SERVED** — figures on load, on page 2, under a filter | fixed |
| `DEF-MET-4954` | Download saves `file.json` holding a 404 | one shared volume on the three services that write or serve it | fixed |
| `DEF-MET-4951` | the paginator slices a Python list | `asset_list` returns a **QuerySet**; `LIMIT`/`OFFSET` reach SQL | fixed |
| `DEF-MET-4962` | four filters run per row; four unbounded reads | the four filters are SQL; the map is batched | partially-fixed |
| `DEF-MET-4955` | three hand-built tables, no toolkit | screens **05a/05b/05c** on the shared `DataTable` | fixed |
| `DEF-MET-4950` | `writeBlockedReason` read nowhere | the two write controls are gated | partially-fixed |
| `DEF-MET-4959` | the map's four selects declare inert utilities | the lie is removed; nothing moves | partially-fixed |
| `DEF-MET-4961` | four descriptions, two sentences each | one sentence, ≤ 6 words, ×11 catalogues | fixed |
| `DEF-MET-4964` | three trailers state an absence the code lacks | all three corrected | fixed |
| `DEF-MET-4963` | three off-scale R11 anchors | **re-measured and it is FIVE**; not swept | partially-fixed |

---

## 1 · `DEF-MET-4953` — THE FOUR FIGURES, AND WHY THIS IS THE PO'S RULING BEING KEPT

**Reproduced first, on `pine-hill`, in Chromium at 1440.** `?tab=meters` drew
**four elements carrying `data-kpi-absent`** over a list reading *1–50 of 110*.
So did page two. So did `?tab=meters&per=200&f.status=uninstalled`, with the
whole six-row filtered set on screen.

`kpiRowsComplete` was **right and is unchanged**: it refuses to show a page's
count as the utility's. What was missing was the read.

**`GET /assets` now carries `kpis`** for the two tabs that draw a grid. It is on
the LIST answer and not its own route, for the reason `api.py` already gives
about `?terms=`: a screen that asked one route for the rows and another for the
strip could draw one tab's figures over another tab's list, and nothing would
ever go red.

**The figures count the TAB, not the query, and that is the EXISTING meaning.**
The client only ever rendered these numbers with no search and no filter, so the
tab's own population is what the four cards have always meant. Narrowing them
with the filter would make *In inventory* and *Meters in service* mutually
exclusive and at most one card non-zero, which is not a strip anybody drew.

**Measured after** (same tenant, same browser):

| address | dashes before | dashes after | the strip now reads |
|---|---|---|---|
| `?tab=meters` | **4** | **0** | Meters in service **104** · 7 masters · 9 subs · 1% AMI |
| `?tab=meters&page=2` | **4** | **0** | identical — it is an estate fact |
| `?tab=meters&f.status=uninstalled` | **4** | **0** | identical |
| `?tab=behind_the_meter&f.status=uninstalled` | **2** | **0** | Devices **15** · Exporting 0 · Exported · August 780 kWh |

**The served numbers are the client's own arithmetic, proved rather than
assumed:** `asset_kpis` was compared with `metersKpis`'s predicates row by row
(`test_kpis_reproduce_the_client_count`), and at `per=200` the browser's own
count before this change read *104 · 7 · 9 · 1%* — the same four numbers.

⚠ **THE TWO WORDLESS TABS STAY WORDLESS.** `D9` (PO, 2026-08-22) replaced the
prose with the grid; ruling 2 of 2026-09-12 (*"a) Fix the figures"*) is what
this is. `AssetRegistry.test.tsx:760-784` still asserts that absence by name and
was not touched. The two dead keys (`assets.explainer.meters`,
`.behind_the_meter`) are still in all eleven catalogues and still reach no
screen; retiring them is a separate act and is **not** done here.

**Cost:** two extra queries on the Meters list answer, one on Behind the meter,
**independent of the tenant's size** (`test_kpis_cost_does_not_move_with_the_tenant`).

---

## 2 · `NFR-3` — THE NUMBERS, BEFORE AND AFTER

Measured with `CaptureQueriesContext` against real Postgres on **`pine-hill`**,
110 meters in the tab. Step 1 measured the same thing on an 11-asset tenant; the
shape is the same and the numbers are thirteen times sharper.

| read | before | after |
|---|---|---|
| `GET /assets` unfiltered | 1 | 2 (the page + its count) |
| …`f.assigned=true` | **111** | **2** |
| …`f.assigned=false` | ignored entirely before `CR-089`; **21** | **2** |
| …`f.service=water` | **209** | **2** |
| …both | **319**, to return 53 rows | **2** |
| `GET /assets/geo` | **241** | **8** |
| `GET /assets/stock` | 6 | 6 (untouched) |
| `GET /assets/lifecycle` | 9 | 9 (untouched) |

**`LIMIT` and `OFFSET` now reach SQL** — asserted on the generated SQL, not
inferred: `… LIMIT 50 OFFSET 50` on a doubly-filtered page.

**How the four filters got into SQL, and it needed no new seam.** Both FKs are
already in B2 §2's reviewed cross-module set — `assets.service_point →
metering.ServicePoint` and `asset_assignments.unit → metering.Unit` — so
`assigned`, `premises_id` and `service` are joins the ORM can express.

⚠ **`test_due` is the one that is not a join, and it is worth reading.** It is
`add_months(last_test_date, n) <= today`, and `add_months` CLAMPS the day to the
target month's length. No portable ORM expression does that: a 30-day
`timedelta` is a different answer, and `INTERVAL` is spelled differently on
Postgres and on the SQLite the suite runs — which is hard-won law 14's shape
exactly, a version that would be green on every machine and wrong on the one
that matters. So the comparison is done in whole months, which both databases
can do:

```
today >= add_months(d, n)
  ⟺  elapsed > n  OR  (elapsed == n AND today.day >= min(d.day, days_in(today)))
```

and the second half collapses to a constant the caller already knows, because
`today.day >= days_in(today)` is only true on the last day of a month.

**It is not assumed to agree with `test_due()` — it is compared with it**, row
by row, over seven cadences (including 31 Jan + 1 month, a leap day, and a
0-month cadence) across **66 simulated `today`s spanning fourteen months**.

**What is NOT fixed, and the row stays `partially-fixed` for it:**
`GET /assets/stock`, `GET /assets/lifecycle` and `GET /assets/geo` still take
**no page parameter at all**. `geo_view` no longer costs a query per marker, but
it still answers the whole estate in one payload. Bounding those three is server
work with a real design question behind it (a viewport? an area filter?) and is
not slipped into a fix pass.

---

## 3 · `DEF-MET-4954` — THE DOWNLOAD

**Not reproduced locally, on purpose, and the reason is the defect.**
`config.settings.local` defaults `JOBS_EAGER` to **true**, so the job runs
in-process and the download succeeds — which would prove nothing about a
deployment that sets it false. `.env.example:183` ships `JOBS_EAGER=false`.

The two halves were each written down and nobody added them up: the worker
writes the CSV to its own `/app/var/artifacts` and the web process serves a 404
from an empty directory of the same name, which Chrome saves as `file.json`.

**Fixed:** one named `artifacts:` volume, mounted at the same path on
**`backend`** (which serves), **`celery`** (the list/asset CSV and the audit-log
export) and **`celery-billing`** (the bill print set). The file had **no
top-level `volumes:` key at all** before this.

**And the runbook's trigger was wrong in the same direction the compose comment
was.** `09-infra/02 §10.6`, §2.5 and §8 all made the shared mount *"required the
moment web `desiredCount > 1`"*. The true condition is **`JOBS_EAGER=false`**,
which production sets, so the mitigation stayed parked at one replica while the
feature was broken for everyone. All three now say so.

**The check that would have caught it** asserts the JOIN rather than either
half: the three services must mount the **same named volume at the same path**,
and the source must be declared under the top-level key. It is deliberately not
*"does `backend` have a volume"*, which passes the moment anybody adds any mount
for any reason.

---

## 4 · `DEF-MET-4955` — SCREENS 05a / 05b / 05c

**The as-built, measured in a browser before the rebuild: 3 tables · 0 sortable
headers · 0 pagination footers · 0 search boxes · 1 row-action control in the
whole tab.** Built to the drawings, walked at **1440 and 1280**:

| | 05a certifications | 05b warranty | 05c forecast |
|---|---|---|---|
| sortable headers | **2** (Asset, Due) | **3** | **3** |
| search prompt | *Search asset # or premises…* | *Search supplier or asset group…* | *Search asset group…* |
| filter | Status ×4 | Cover ×3 | Attention ×2 |
| column chooser | ✓ | ✓ | ✓ |
| pager | *1–2 of 2* + sizes + ‹ › | *1–9 of 9* | *1–9 of 9* |
| row actions | **2** (wrench, eye) | 1 (eye) | 1 (eye) |
| empty state | ✓ | ✓ | **✓ — the branch that did not exist** |

**Proved it actually works, not merely that it renders:** searching *Neptune* on
05b took the list from **1–9 of 9** to **1–2 of 2**, returning the two Neptune
rows. Default sort on 05a is **Due ascending**, as drawn.

**`?section=` is URL state** (BR-SHL-011), so each of the three is linkable; an
unknown value lands on the default rather than a blank screen.

### 4a · Two carry-over decisions the blueprint left open — DECIDED

Screen 05c's carry-over does not close its own arithmetic (ten as-built
elements, then nine unchanged + one relabelled + one removed = eleven). The two
it never dispositions:

1. **The Programme total SURVIVES**, beneath the table rather than inside it. It
   is a real served pair with no other home, and putting a total row inside a
   `DataTable` would mean a second table — the rule-36 breach this rebuild
   exists to end. It reads *12-month replacement programme · 3 · $513.00*.
2. **The Turn into work panel SURVIVES**, on the forecast section. Not listed as
   removed, its button is live, and the forecast is what its sentence is about.

### 4b · The Asset value panel is REMOVED, and that costs something

PO instruction, 2026-09-11, quoting the panel in full: ***"remove this - Asset
value"***. It is the only field-bearing removal in the whole blueprint.
**`buy_value` and `present_value` are computed nowhere else in the product**, so
a person who used them loses them entirely. The server still serves
`asset_value`; nothing renders it. The test that asserted the panel's presence
is **inverted rather than deleted**, so restoring it by accident goes red.

### 4c · One defect found by the rebuild's own tests

`loading={view.isFetching}` drew **eight skeleton bars over a populated table**
on every background refetch. `tsc`, eslint and the browser walk all passed over
it — in a browser the fetch has settled before anybody looks. The SSR test
caught it. It is `loading={false}` now, which is correct because reaching that
line means the data is defined.

---

## 5 · `DEF-MET-4950` — AND WHERE THIS LANE DISAGREES WITH ITS OWN ROW

The row names **three** controls. **Two are fixed:** the Lifecycle wrench (it
opens the raise-work-order form, which writes) and *Set up an exchange rule*
(it promises a write). Both now render disabled carrying the reason, asserted in
a DOM test that reads the control's `disabled` attribute rather than the prop.

**The third is NOT a breach and is deliberately not gated.** `Parts in Work →`
navigates to the parts REGISTER — a read screen a read-only role may open.
BR-SHL-025 gates *forbidden actions*; gating this would hide a capability the
role has. Step 1 §5.3 reached the same conclusion from the rule's own words and
`AssetInventoryTab.tsx:72-74` says as much about itself. **Recorded as a
disagreement rather than quietly skipped**, which is why the row is
`partially-fixed` and not `fixed`.

---

## 6 · `DEF-MET-4959` — THE MAP'S SELECTS: EVERY UTILITY WAS INERT

Measured on the element itself, at 1440, before the change:

| | declared | rendered |
|---|---|---|
| `min-h-8` | 32px | **36px** |
| `px-2 py-1` | 4/8px | **6px 30px 6px 10px** |
| `text-sm` | 12px | **14px** |
| appearance | (unset) | `none`, with the product's chevron |

`.view select` supplies all four and outranks a single-class utility. **The
rendered values are the right ones** (36px is the product's control height),
which makes the declarations a lie rather than a loss. They are removed and NOT
replaced with higher-specificity copies — winning would give the map four 32px
controls in a product of 36px ones. Nothing moves; proved by reading the
computed styles of all four selects before and after.

**What is NOT fixed:** the chevron and the height still come from an ancestor
these controls never ask for. That is true of **every `<select>` in the
product** — `DataTable`'s page-size control and `ChipMultiSelect`'s adder
included — so it is a kit-wide question, not this component's to answer inside
an Assets pass. Hence `partially-fixed`.

---

## 7 · `DEF-MET-4961` — AND THE GATE IT COLLIDED WITH

Four rendered descriptions, each cut to **one sentence of six words or fewer**,
in all eleven catalogues, written in each language rather than translated from
the English (B14 rule 35). **Four changed lines per catalogue, eleven
catalogues** — applied through `10-scripts/i18n_fanin.py`, the tool that owns
those files, so no catalogue was re-serialised.

| tab | was | is |
|---|---|---|
| Sub-meters | 24 words, 2 sentences | *Sub-meters bill their own unit.* (5) |
| Inventory | 18 words, 2 sentences | *Assets you own, not yet installed.* (6) |
| Lifecycle | 9 words, 1 sentence | *What falls due, what wears out.* (6) |
| Map | 23 words, 2 sentences | *Every asset on real streets.* (5) |

⚠ **`G14` PINS `assets.explainer.sub_meters` TO r10'S SENTENCE, SO THIS IS A
SUPERSESSION AND IT IS STAMPED RATHER THAN SLIPPED.** `DEF-527` adopted r10's
24-word pair on **2026-08-22**; **B14 rule 32 was ratified on 2026-08-31** and
rule 33 before it, and both are later law. `CLAUDE.md` settles which authority
wins: r10's `UI-RULES.md` *"is its SOURCE, not its authority — B14 wins and
every divergence is stamped there."* `EXPLAINERS_NOT_IN_R10` moves **2 → 3** in
the same commit, with the key, the rules and the reasoning written on the
constant. A fourth still goes red.

**Raising a baseline is normally the most damaging move available**, so the bar
for it is a named key, a named rule that outranks r10, and the wording in the
same commit. All three are met and the alternative was leaving a ratified copy
rule broken.

---

## 8 · `DEF-MET-4963` — RE-MEASURED, AND IT IS FIVE, NOT THREE

Measured with `getComputedStyle` at **1920, 1440 and 1280**:

| anchor | value | on the R11 scale? |
|---|---|---|
| `.side-item` padding / gap | `9px 12px` / `10px` | **no** (both widths) |
| the status pill | `2px 9px` / gap `5px` | **no** |
| `main.view` **≤1440** | `24px 24px 56px` | the 56 is **no** |
| `main.view` **>1440** | `28px 32px 64px` | **28 and 64 are also no** — the row does not name these |
| `.card` | `padding: 28px` | **no** — not in the row at all |

**Nothing is swept, and that is the decision rather than a deferral.** All five
live in the SHELL (`AppShell.css`, `StateFrame.css`) and reach **every screen in
the product**. The row's own prevention says a sweep that moves them without a
decision is how a product acquires a fourth — and re-measuring found the fourth
and fifth before anyone swept. This is the same shape as the four shared-table
rows the PO ruled out of scope on 2026-09-12: a change reaching the whole
product is not a risk to take inside an Assets pass. **Stated, not made.**

What this lane contributes is the corrected measurement: the row said three, at
one width. It is five, and two of them only appear above 1440.

---

## 9 · WHAT COULD NOT BE CHECKED, WITH ITS NUMBER

1. **The genuinely-empty forecast state: 0 of 1 walked in a browser.** Every
   tenant has forecast rows, so the state is unreachable from the screen. It is
   asserted in a test against an empty payload instead. (Searching for a
   nonsense term gives the kit's *no results* state, which is a different and
   correct sentence.)
2. **`AST-B-20` end to end: not reproduced.** See §3 — the local settings make
   it impossible to reproduce and impossible to disprove.
3. **Read-only-role RENDERING: not walked in a browser.** The session was System
   Admin. The two gated controls are asserted in a DOM test that reads the
   rendered `disabled` attribute, which is the honest half.
4. **Paging beyond one page on 05a/05b/05c: not exercised.** The largest section
   holds 9 rows against a 50-row page. The pager renders; it was not paged.
5. **Below 1280: not measured, deliberately.** Assets is a clerk and
   utility-admin surface (PO ruling 2026-09-10).
6. **Screen 07, the bulk-assign dialog: 0 states walked** — every route in
   starts a write.
7. **The Imports tab: untouched, out of scope.**

## 9a · THE ONE GATE NUMBER THIS LANE MOVED, AND IT IS +1

**`G67` (fix-leaves-a-trace) goes 220 → 221.** It fails when a row marked closed
names a file and that file never mentions the id — *"so a lane grepping for it
finds nothing and concludes the fix was never made"*. Nine of my ten rows are
traced: the defect id is written into every file its row names, including four
files this lane did NOT otherwise change (`tenancy/exports.py` and
`tenancy/api.py` for the 404's two halves, `FormModal.css` and `AppShell.tsx`
for the class whose reach IS the finding, `AppShell.css` and `StateFrame.css`
for the anchors measured and deliberately not swept).

**The tenth cannot be traced and the reason is mechanical:** `DEF-MET-4961`'s
surface names `07-frontend/src/i18n/locales/en.json`, and **JSON carries no
comments.** The gate's second remedy is to correct the row's surface, and the
register's own tools refuse to edit any column but `status` and `fixed_commit`
— deliberately, because a hand-edit of a 2,600-row register is the whole reason
those tools exist. So the honest outcome is +1, written down here rather than
worked around. The rendering site (`AssetRegistryPage.tsx`) does name the id, so
a person grepping the code finds it; only the catalogue cannot say so.

⚠ **EVERYTHING ELSE THE SUITE REPORTS WAS ALREADY RED.** `run_gates` at the tip
this lane started from is **75 PASS / 43 FAIL / 5 SKIP — MERGE BLOCKED**, and
the set of failing gates is byte-identical before and after this lane's work.
`G14` fails on one thing both before and after (its column-heading ratchet at
368 against a baseline of 199) and its EXPLAINER half is green with the 2 → 3
supersession in §7. `G15` went 266 → 267 mid-lane and is back at **266**: three
of my nineteen new values happened to be the same word in English (German and
Indonesian *Status*, French *Attention*), so `filter.status` was dropped in
favour of the `col.status` key the catalogue already had — one string instead
of two — and *Attention* became **Replacement**, which is both translatable and
a better name for a filter offering *Past life* and *Due within 12 months*.

## 9b · TWO THINGS THIS LANE GOT WRONG, BOTH CAUGHT BY ITS OWN CHECKS

Recorded because the way each was caught is the useful half.

**1 · The rebuilt tables blanked themselves on every background refetch.** All
three were handed `loading={view.isFetching}`, so a stale-then-refetch cycle drew
**eight skeleton bars over a populated table**, on a timer. `tsc`, eslint AND a
browser walk at 1440 all passed over it — **in a browser the fetch has settled
before anybody looks**. The server-rendered test is what saw it, which is the
usual lesson running backwards: here the suite caught what the walk could not.

**2 · The `geo_view` cost case measured a cost nothing paid, twice.** It passed
`unit=` (the unit of MEASURE) where it meant `unit_id` (the unit an asset stands
at), so three meters had a uuid for a UoM and stood nowhere; `geo_view` found no
seats, answered zero markers, and the per-marker cost it exists to measure was
never incurred. Fixing that exposed the second half: `install_date` is REQUIRED
whenever `unit_id` is given (BR-AST-011 assign-on-create) and `create_asset`
refuses without it. **The existing geo fixture in `test_cr028_new_tabs.py`
passes both**, and copying half of a working fixture is how a case spends two
runs failing for a reason that is not its subject. Both are named in the test.

## 10 · DATA

**Nothing was seeded.** Every figure above is over rows that were already there:
`pine-hill` 135 assets / 110 meters, `oak-ridge` 74, `brazosbend` 14. One
write was made to the development database and it was not data: `users
.locked_until` was cleared for the sign-in account after repeated browser
sessions tripped the lockout.

## Trace

* **Packet:** `CR-092-BRC01` §3a §4 §6a §6b §6c · the drawn screens 01–06 in
  `wireframes/CR-092-assets-screens.html` and the PDF rendering of the same
  document · the step-1 conformance file beside this one · `B14` · `NFR-3` ·
  `NFR-5` · `BR-SHL-025` · `BR-SHL-011` · `BR-AST-003/007/031/047`.
* **Built and measured at** `ce623f444`, 2026-09-12, on a stack booted per
  `10-scripts/11-smoke-stack.sh` on private ports 8531/8532, at 1920, 1440
  and 1280.
* **Status:** step 2 complete for this lane. Six rows fixed, four
  partially-fixed with what remains named on each.
