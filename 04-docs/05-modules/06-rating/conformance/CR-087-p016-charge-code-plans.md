# 05 · Charge code → View · Plans — THE DRAWN SPEC

`CHG-01 (charge)` · route `/:tenant/plans-rates/charge-codes/:id?tab=plans` ·
**blueprint pages 16–18**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section
`01 CHARGE CODES`, screen `05`. The screen head and the frame are on **page 16**,
the frame's table finishes at the top of **page 17**, the specification runs to
the top of **page 18**. Read as RENDERED pages — the four-column table and the
`TWO ROUTES` callout are drawn.

**State chips on the screen head:** `EXISTS BEHIND` · `NO COMMITMENT`
**Screen question, verbatim:** *"Where does this charge actually reach
customers?"*

**What this file is.** Only the **bordered grey frame on pages 16–17** is the
specification. The amber *"What was wrong"* block is the problem statement:
*"The tab said it could not name the plans, over a headline count that read 0 for
a code reaching 132 units as a rate schedule's base."*

⚠ **THE `EXISTS BEHIND` CHIP IS FALSE FOR THIS SCREEN AT 2.234.19.** Page 2
defines it as *"the screen is drawn and the data behind it is served"*. Nothing
serves a per-plan reach list — see the diff.

⚠ **B14 rule 37** — `SCW-RES`, `74`, `12`, `132`, `218` and `6 plans` are
ILLUSTRATIONS. None is recorded as a requirement.

---

## 1 · Header — identical to screen 04, `Plans` tab active

| slot | drawn |
|---|---|
| back link | `← Charge codes` |
| kicker | `CHARGE CODE · CONN · ONE-TIME` |
| title (H1) | `Connection fee` |
| status | `ACTIVE` *(pill)* |
| sub-line | `GL account 4200-01 — Connection revenue · Applying it creates a billable item that references the version in force, so an issued bill never changes.` |
| actions | `Duplicate` · `Edit` · `Retire` *(danger)* |

## 2 · Tabs — THREE, `Plans` active

`Overview` | `Plans` | `Audit`

## 3 · The tab description line

`Where this charge reaches customers.`

## 4 · Tiles and the `NOT WORKED OUT YET` band — unchanged from screen 04

The same four tiles (`AMOUNT` · `UNITS REACHED` · `CLASSES` · `STATUS`) and the
same two-row absence band are drawn above the tab body on this tab too. They are
page-level, not per-tab. See `CR-087-p013-charge-code-overview.md` §5–§6.

## 5 · The panel — `Where this reaches`

**Sub-line:** `Every plan that carries this code, and how it gets there.`

## 6 · The table — FOUR columns, no action column

| # | header | alignment | cell, as drawn |
|---|---|---|---|
| 1 | `PLAN` | left | `Sample — Residential` |
| 2 | `CODE` | left | `SCW-RES` · `—` |
| 3 | `REACHED BY` | left | `Named on the plan` · `The base of a rate schedule` **(bold)** |
| 4 | `UNITS` | right | `74` |

**The three drawn rows, in order:**

| PLAN | CODE | REACHED BY | UNITS |
|---|---|---|---|
| `Sample — Residential` | `SCW-RES` | `Named on the plan` | `74` |
| `Sample — Commercial` | `SCW-COM` | `Named on the plan` | `12` |
| `Sample — Residential water` | `—` | `The base of a rate schedule` | `132` |

**No row actions, no header checkbox, no pagination footer are drawn** — see §11.

## 7 · The accent callout under the table

| kicker | `TWO ROUTES` |
|---|---|
| body | `A charge code reaches a customer by two routes: named on a plan, or read as the base of a rate schedule that a plan carries. Both are counted here, and they behave differently under a change.` |

## 8 · States — the blueprint's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **Nothing carries it** | *"`No plan carries this charge code, and no rate schedule reads it as a base.` Both routes named, so a zero is not ambiguous."* |
| **Reached only as a base** | *"The plan column shows the schedule's plans; the code column is a dash, because the plan does not name this code."* |
| **Beyond one page** | *"States how many were checked out of how many **carrying this code** — never out of every plan in the utility."* |

## 9 · Components named in the frame

`Panel` `ReachTable` `Callout accent`

## 10 · FOR · HOW YOU GET HERE · REACHED BY (page 17)

* **FOR** — *"A clerk about to change a price, asking the only question that
  matters first: *who does this hit?*"*
* **HOW YOU GET HERE** — *"The **Plans** tab."*
* **PRIMARY ACTION** — *"None. This tab exists to be read before a decision is
  made elsewhere."*
* **WHAT CHANGED** — *"This tab used to say it could not name anything — one
  sentence reading *the tile above counts the plans; naming them one by one needs
  a read that does not exist yet*, over a screen whose whole job is to answer
  that. Worse, the count above it read **0** for a code that was every water
  size's base, because only the plan route was counted."*
* **REACHED BY** — *"Two routes behave differently under a change: renaming a
  plan's charge is local; changing a base moves every size on a schedule. Naming
  the route is what stops a clerk mistaking one for the other."*

## 11 · Absences — drawn as absent, do not fill them

* **No row actions** — nothing on a row navigates or acts.
* **No toolbar** — no search, no filter chips, no column chooser.
* **No pagination footer is DRAWN**, but §8's *Beyond one page* state requires
  one and names what its sentence must count. Both are recorded; see the
  divergence below.
* **No `Service` column, no `Amount` column** — a plan carries the code, and what
  it costs is Overview's grid.

---

## THE DIFF — the drawn frame against the code at 2.234.19

The tab body is `DefinitionTabBody` in
`07-frontend/src/features/rating/DefinitionDetailPage.tsx`, **lines 681–766**.

### 1 · THE TABLE DOES NOT EXIST. THE TAB IS ONE SENTENCE SAYING SO.

`DefinitionDetailPage.tsx:725–729`:

```
if (props.tab === PLANS_TAB) {
  // The KPI tile says HOW MANY plans carry it (`used_by_plans`, served). WHICH
  // plans is a different read and no route answers it.
  return <ArrivesWith title={heading} message={t("rating.definition.plans.arrivesWith")} />;
}
```

`rating.definition.plans.arrivesWith` (`07-frontend/src/i18n/locales/en.json`) =
**"The tile above counts the plans that carry this definition. Naming them one by
one needs a read that does not exist yet."**

That is, word for word, the sentence the blueprint quotes as *"what was wrong"*.
**Verified live at 2.234.19.**

`rating.definition.panel.plans` = `Plans` is the panel title it renders; the
drawn panel title is `Where this reaches` and its sub-line
`Every plan that carries this code, and how it gets there.` — neither exists as a
key.

### 2 · NO ENDPOINT SERVES THE REACH LIST

`06-backend/apps/rating/api.py:774–776` is the whole of the charge surface:

```
path("charges", charges),
path("charges/<str:charge_id>", charge_item),
path("charges/<str:charge_id>/deactivate", charge_deactivate),
```

There is no `charges/{id}/plans`. The rate schedule and the discount each have
their own extra reads (`rate-schedules/{id}/versions`, `discounts/{id}/versions`,
`plans/{id}/units` at `:761`); the charge has none. **So the `EXISTS BEHIND` chip
is wrong for this screen** — this is a new server read, not a front-end job.

### 3 · THE `0` THE BLUEPRINT DESCRIBES IS REAL, AND HERE IS THE LINE

`06-backend/apps/rating/selectors.py:2559–2571`:

```
def charge_used_by(charge: models.Charge) -> dict[str, Any]:
    plans = models.PlanChargeRule.objects.filter(tenant_id=_tenant_id(), charge=charge).count()
    return {"plans": plans, "invoice_lines": seams.invoice_line_references(charge.id)}
```

**Only `PlanChargeRule` — the *named on the plan* route.** The second route is
real: a charge code declares itself its service's base with `Charge.is_base`
(`06-backend/apps/rating/models.py:834`), and a rate schedule reads its base from
that code rather than carrying its own —
`models.py:437–440`: *"`tariff_versions.base_charge` and the plan's own base both
stop being sources — §A3's 'one source, two surfaces': the rate matrix DISPLAYS
this value, attributed (`$12.00 · from BASE-W`), and cannot edit it."*
A base code that no plan names therefore counts **0** while it prices every
connection on its service. **Confirmed by reading the selector, not inferred.**

⚠ This is the same count the Overview's tile 1 renders as `Plans carrying it`
(`definitionDetail.tsx:483–485`). The blueprint's *"the count said accounts"*
(screen 04, WHAT CHANGED 2) does **not** match the code at 2.234.19 — the tile
says PLANS, not accounts. What is wrong with it is the undercount above, not the
noun. Recorded so nobody fixes a noun that is already right.

### 4 · THE `UNITS` COLUMN AND THE `UNITS REACHED` TILE ARE ONE QUERY

Both need units on a current plan assignment. **The query exists for the
discount** — `discount_offered_unit_count`,
`06-backend/apps/rating/selectors.py:3255–3300` — and its docstring already
carries the ruling this frame's *"units, not accounts"* is quoting
(`DEF-RAT-4664`). `plans/{plan_id}/units` (`api.py:761`, CR-087 D5 · PRB-21)
is the per-plan half.

### 5 · WHAT IS ALREADY RIGHT

* The tab id `plans` resolves: `DEFINITION_TABS.charge` includes it
  (`definitionDetail.tsx:67`), so the drawn address
  `…/charge-codes/:id?tab=plans` opens the right tab
  (`DefinitionDetailPage.tsx:131–134`, `:269`).
* `PLANS_TAB` is a named constant (`definitionDetail.tsx:145`), so the branch
  cannot drift.
* The tiles and the header above the tab body are page-level exactly as drawn
  (`DefinitionDetailPage.tsx:605` sits above `:608–615`).

---

## DIVERGENCES — B14 rule 38 and B14 rule 16

1. **THE FRAME DRAWS NO PAGINATION FOOTER AND B14 RULE 16 REQUIRES ONE.**
   Rule 16: *"Pagination footer on every list table: `Showing 1–50 of N · Rows per
   page 50/100/200/500/1000 · ⇤ ← Page x of y → ⇥`"*, and it rides the shared
   `DataTable`. The frame's own *Beyond one page* state asks for a count sentence
   with a specific denominator. **The UI rules win on the FOOTER; the drawing wins
   on WHAT THE SENTENCE COUNTS** — *"how many were checked out of how many
   carrying this code — never out of every plan in the utility"*.
2. **`ReachTable` IS NOT A KIT COMPONENT AND MUST NOT BECOME A SECOND TABLE.**
   B14 rule 36 and the skill's never-do list: a second table is a defect, not a
   contribution. `components/DataTable.tsx` is the shared one. Recorded as a
   naming divergence only — the frame's `ReachTable` is a description of content,
   not a licence for a new component.
3. **NFR-3 APPLIES TO THIS LIST FROM ITS FIRST COMMIT.** `CLAUDE.md`: universal
   server pagination, no unpaginated list, no per-tenant cap. A code carried by
   every plan in a 40,000-account utility is exactly the list `NFR-3` exists for.

---

## THE BLUEPRINT AGAINST ITSELF — recorded, not resolved

1. **THE `EXISTS BEHIND` CHIP CONTRADICTS THE FRAME'S OWN WHAT-CHANGED TEXT.**
   The chip says the data is served; the WHAT CHANGED paragraph says the read
   *"does not exist yet"* was the problem and the whole table is new. Both are on
   pages 16–17.
2. **THE `CODE` COLUMN HOLDS THE PLAN'S CODE, NOT THE CHARGE CODE'S**, on a
   screen whose every other surface uses `CODE` for the charge code (`CONN` in
   the kicker, `CODE` in the wizard's review grid). Recorded; the header word may
   need to be `PLAN CODE`.

---

## FOR THE PRODUCT OWNER

* **The `Beyond one page` sentence is a new denominator.** Our shared pager says
  *"Showing 1–50 of N"* where N is the filtered total. The frame asks for *"how
  many were checked out of how many carrying this code"*. If the two are the same
  number the pager already says it; if they are not, this is a second sentence
  beside the pager and B14 rule 32's one-sentence budget decides where it goes.
  One question, one figure.

---

## WHAT COULD NOT BE VERIFIED WITHOUT THE APP RUNNING

* Whether the drawn `UNITS` column is right-aligned. The render reads
  right-of-centre and the three values are short; alignment at this size is not
  conclusive from a 2× page raster.
* The three drawn states (`Nothing carries it`, `Reached only as a base`,
  `Beyond one page`) cannot be exercised at all — the tab renders one sentence.

## THE ELEVEN CATALOGUES

`rating.definition.plans.arrivesWith` and `rating.definition.panel.plans` are
present in all eleven locales. `plans.arrivesWith` is **English verbatim** in
`es-MX`, `hi`, `id-ID`, `ja-JP` and `ko-KR` — B14 rule 35. Every key the drawn
table needs (`Where this reaches`, `PLAN`, `CODE`, `REACHED BY`, `UNITS`,
`Named on the plan`, `The base of a rate schedule`, `TWO ROUTES` and its body,
and the three state sentences) **does not exist in any locale**.

---

## ⚠ AMENDED 2026-09-10 — THIS TAB IS BUILT

**PO ruling 2026-09-10, verbatim: *"build"*** (decision log, *THE FOUR EMPTY TAB
BODIES GET BUILT*), executed as `CR-087` maintenance. `DEF-RAT-4832`.

| §  | finding | now |
|---|---|---|
| §1 | the tab is ONE SENTENCE saying it cannot name a plan | **BUILT** — the drawn four-column table, in a panel headed `Where this reaches` with the drawn sub-line |
| §2 | no endpoint serves the reach list | **BUILT** — `GET /charges/{id}/plans`, `apps/rating/api.charge_plans`, over `selectors.charge_reach_queryset` + `charge_reach_rows` |
| §3 | the count sees only the NAMED route, so a base code reads `0` | **FIXED IN THE READ** — `charge_reach_plan_ids` returns both sets and every row names its own route as a WORD. ⚠ **`charge_used_by` IS DELIBERATELY UNTOUCHED**: it feeds the DELETE lock, and widening a lock is a different decision from widening a screen count. **So the Overview TILE still undercounts** — that one is a separate change with its own reasoning |
| §4 | the `UNITS` column and the tile are one query | **BUILT for the column** — units on a CURRENT plan assignment (`assigned_to IS NULL`), one grouped count for the whole page rather than one per row |
| divergence 1 | the frame draws no pagination footer and B14 rule 16 requires one | **RULE 16 WINS** — `ListPager`, server-paged, and the served `count` is the whole set (`NFR-3`). The DRAWING wins on what the sentence counts, and the served count is exactly *"how many carrying this code"* |
| divergence 2 | `ReachTable` must not become a second table | **HONOURED** — no new component; the same table skin `PlanDetail` and `RateScheduleDetail` already draw |
| against-itself 2 | the `CODE` column holds the PLAN's code on a screen where `CODE` means the charge's | **RESOLVED as `Plan code`** — one word, and it stops a clerk reading one as the other. Recorded as a divergence from the drawn header |

**Still open, and named rather than built:**

* the drawn `Beyond one page` sentence asks for a denominator beside the pager.
  Our pager already says *"Showing 1–50 of N"* where N is the whole set carrying
  this code, which is the same number — so **no second sentence was added** and
  B14 rule 32's one-sentence budget is kept. If the PO wants the drawn wording,
  it is a copy change to `ListPager` and not to this screen.
* the tile above the tab still counts one route (see §3 above).
