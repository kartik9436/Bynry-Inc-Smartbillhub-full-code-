# 18 · Rate schedule → View · Overview — THE DRAWN SPEC

`S11 · RAT-02` · route `/:tenant/plans-rates/rates/:id` · **blueprint pages 55–58**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section opening
on page 55, **frame drawn across pages 55–57**, specified on 57–58. Read as
RENDERED pages — the eyebrow's five parts, the THREE-tab strip, the four tiles
with the absence band beneath them, and the rate table whose last three column
headings are usage BLOCKS are only visible as a picture.

**State chip:** `NEW BUILD`
**Commitment:** `PRB-08`. Screens `14` · `18`.

**Masthead warning, applied.** As-built at **2.232.0**; re-checked at **2.234.19**.

---

## 1 · Header

| slot | drawn |
|---|---|
| back | `← Rate schedules` |
| kicker (eyebrow) | `RATE SCHEDULE · WATER · RESIDENTIAL · TIERED · V3` — **FIVE parts** |
| title (H1) | `Sample — Residential water (inclining tiers)` |
| status pill | `ACTIVE` |
| sub-line | `In force from 06/01/2026 · GL account 4100-01 — Water revenue · Rate changes save as a new version; a version in force is never edited.` |

⚠ **THE EYEBROW'S THIRD PART IS THE CUSTOMER CLASS.** Page 57: *"It was on no
screen at all — not the header, not a field, not the list. It is in the eyebrow
beside the service **and** it is a field in its own right, because it decides which
base charge applies and therefore what a customer pays. A schedule with no class
says `every class` rather than nothing."*

⚠ **B14 rule 37 — `V3`, `06/01/2026`, `4100-01` and the schedule name are
ILLUSTRATIONS.**

## 2 · Header actions — three, top-right, in this order

| # | label | tier |
|---|---|---|
| 1 | `Duplicate` | secondary |
| 2 | `Edit` | secondary |
| 3 | `Retire` | **danger** (outline accent) |

## 3 · Tabs — THREE, in this order, `Overview` active

`Overview` | `Plans` | `Audit`

⚠ **FIVE TABS BECOME THREE.** Page 57: *"Overview, Rate matrix and Billing rules
were three tabs answering one question. A clerk checking a price opened Overview,
saw a chart and no numbers, and went to Rate matrix; a clerk asking how a quantity
becomes money went to a third. They are one tab in four blocks, ordered the way a
person arrives: **what it prices** (identity), **the rates** (the chart and every
row), **how it bills** (behaviour and where money is posted), **what it may and may
not do** (policy). Five tabs are three."*

**Tab explainer, one sentence, beneath the strip:**
`What this schedule prices, for whom, and at what.`

## 4 · Tiles — four, and they are drawn on ALL THREE tabs

| # | label | value | detail line |
|---|---|---|---|
| 1 | `IN FORCE` | `v3` | `from 06/01/2026` |
| 2 | `UNITS` | `74` | `across 3 plans` |
| 3 | `SIZES` | `9` | `all priced the same` |
| 4 | `NEXT CHANGE` | `01/01/2027` | `+4.0%, filed` |

**Absence band beneath the tiles, ruled off:**

| legend | label | sentence |
|---|---|---|
| `NOT WORKED OUT YET` | `Revenue` | `Nothing totals billed revenue for one rate schedule.` |

⚠ **THE TWO EM-DASH TILES ARE THE NAMED DEFECT.** Page 58: *"`Sizes` read an
em-dash saying sizes are not priced separately while the list claimed 9 sizes; both
now say `9 sizes, all priced the same`. `Revenue` moves to the absence line. In
their place: which version is in force, and whether a change is already dated."*

## 5 · Block 1 — `What it prices`

**Heading:** `What it prices` · a field grid, three fields across then one below

| # | label | value | sub-line |
|---|---|---|---|
| 1 | `SERVICE` | `Water` | — |
| 2 | `CUSTOMER CLASS` | `Residential` | `Only accounts in this class are priced by it.` |
| 3 | `STRUCTURE` | `Tiered` | — |
| 4 | `UNIT OF MEASURE` | `kgal` | `Every price below is in this unit.` |

## 6 · Block 2 — `The rates`

**Heading:** `The rates`
**Hint:** `Every priced row. The block ranges are the column headings, so a price is read where a clerk looks it up.`

| # | header | content |
|---|---|---|
| 1 | `SIZE` | `2"` · `4"` · `6"` |
| 2 | `BASE CHARGE` | amount over quiet code — `$8.0000` / `BASE-W-RES` |
| 3 | `MINIMUM RATE` | `$18.50` · `$24.00` · `—` + `No row — the schedule's single minimum applies.` |
| 4 | `0–2 KGAL` | `$4.4096` on every row |
| 5 | `2–10 KGAL` | `$7.1656` on every row |
| 6 | `10+ KGAL` | `$8.8192` on every row |

⚠ **THE LAST THREE HEADINGS ARE USAGE BLOCKS, NOT TIER NUMBERS.** Page 57:
*"`0–2 kgal · 2–10 kgal · 10+ kgal` rather than `Tier 1 · Tier 2 · Tier 3`. A clerk
looking up a price knows the usage, not the tier number — which is also what the
chart's captions were for, so nothing is lost with it."*

**Closing callout, accent:**

| legend | sentence |
|---|---|
| `WHERE THE BASE COMES FROM` | `The base comes from charge code BASE-W-RES, the one declared for the Residential class. All 74 units are counted in the header; nothing counts units per connection size.` |

⚠ **THERE IS NO `ACCOUNTS` COLUMN, AND THE CALLOUT SAYS WHY.**

⚠ **THE TIER CHART IS GONE.** Page 57: *"The tier chart came out on your
instruction and the table is enough. It plotted three bars a clerk had already read
as numbers on the row beneath, and it could only ever draw one shape — a flat,
seasonal or time-of-use schedule has nothing to stack. … The vertical space it used
goes to rows."*

## 7 · Block 3 — `How it bills`

**Heading:** `How it bills`
**Hint:** `Three behaviours that are the same for every schedule, and where the money is posted.`

| # | label | value | sub-line |
|---|---|---|---|
| 1 | `PART-PERIOD BILLS` | `Prorated automatically` | `Engine behaviour. There is no setting.` |
| 2 | `ROUNDING` | `Two decimals at finalisation` | `One rule for the whole product.` |
| 3 | `CURRENCY` | `USD` | `The utility's own, in Settings.` |
| 4 | `GL ACCOUNT` | `4100-01 — Water revenue` *(monospace)* | `Set in Settings, under Accounting.` |

⚠ **THESE ARE STATED BEHAVIOURS, NOT EMPTY SETTINGS.** This screen's RULES line
adds the clause in so many words: ***"A behaviour is not drawn as an empty
setting."***

## 8 · Block 4 — `What a schedule may and may not do`

**Heading:** `What a schedule may and may not do`
**Hint:** `Fixed behaviour, not settings. Nothing here can be changed on any screen.`

A bulleted list of four:

1. `One service and one class per schedule: this one prices Water for Residential and nothing else.`
2. `Activating a new version supersedes this one from its effective date. A version in force is never edited.`
3. `A draft cannot be attached to a plan until it is activated.`
4. `Once a schedule has billed or is referenced by a plan it can be retired but not deleted.`

## 9 · States — verbatim

| state | drawn behaviour |
|---|---|
| **No version in force** | *"The header reads `no version is in force yet` and the rates block says `no pricing entered yet` rather than an empty table."* |
| **No class set** | *"`Every customer class`, and the base block says which code resolves where more than one could."* |
| **Sizes priced differently** | *"`9 sizes, 2 priced differently` — the same wording the list uses, from the same source."* |
| **Unit mismatch** | *"A strip above the blocks: this schedule prices in one unit and the service is billed in another with no conversion on file."* |
| **Read-only role** | *"A role that may read but not change Plans & Rates sees every figure and no button. The refusal names the role, not the screen."* |

## 10 · Components named in the frame

`PageHeader` `KPIStrip` `AbsenceBar` `RateMatrix` `Panel` `FieldGrid` `PolicyList`

## 11 · FOR · HOW YOU GET HERE · PRIMARY ACTION · COGNITIVE LOAD

* **FOR** — *"Anyone asking what a service costs — a clerk on the phone, a supervisor checking a query, a new starter learning the tariff."*
* **HOW YOU GET HERE** — *"`Rate schedules` tab, clicking the name. Also from a plan's Rate schedules tab and a charge code's Where-this-reaches tab."*
* **PRIMARY ACTION** — `Edit.`
* **COGNITIVE LOAD** — *"Four blocks with one-line intros, so a reader learns the shape before reading a value. Nothing repeats between blocks, and the behaviours are grouped precisely so they are not mistaken for unset settings."*
* **RULES, extra clauses** — *"One fact has one wording everywhere. A behaviour is not drawn as an empty setting."*

---

# THE DIFF — drawing against the code at 2.234.19

Code: `07-frontend/src/features/rating/RateScheduleDetail.tsx`.

## D1 · FIVE TABS, NOT THREE

`RateScheduleDetail.tsx:180-186`

```tsx
export const RATE_DETAIL_TABS = [
  "overview",
  "matrix",
  "billing-rules",
  "plans",
  "versions",
] as const;
```

| drawn | built | label key |
|---|---|---|
| `Overview` | `Overview` | `rating.rateDetail.tab.overview` |
| — | `Rate matrix` | `rating.rateDetail.tab.matrix` |
| — | `Billing rules` | `rating.rateDetail.tab.billing-rules` |
| `Plans` | `Plans` | `rating.rateDetail.tab.plans` |
| `Audit` | `Versions & filings` | `rating.rateDetail.tab.versions` |

The tab is URL state (`?tab=`), so the drawn `?tab=audit` is `?tab=versions` today
— page 61 draws `/:tenant/plans-rates/rates/:id?tab=audit`. Route rows live in
`07-frontend/src/routing/screenIds.ts:694-699`.

## D2 · THE FOUR TILES ARE THE WRONG FOUR, AND TWO OF THEM ARE HARD-CODED EM-DASHES

`RateScheduleDetail.tsx:712-737`

```tsx
  const kpis: readonly KpiTile[] = [
    { id: "accounts", label: t("rating.rateDetail.kpi.accounts"), value: detail.applied_to_accounts },
    { id: "plans", label: t("rating.rateDetail.kpi.plans"), value: detail.used_by_plans },
    { id: "sizes", label: t("rating.rateDetail.kpi.sizes"), value: "—",
      detail: t("rating.rateDetail.kpi.sizesAbsent") },
    { id: "revenue", label: t("rating.rateDetail.kpi.revenue"), value: "—",
      detail: t("rating.rateDetail.kpi.revenueAbsent") },
  ];
```

| # | drawn | built |
|---|---|---|
| 1 | `IN FORCE` `v3` / `from 06/01/2026` | **absent** |
| 2 | `UNITS` `74` / `across 3 plans` | two separate tiles, `Accounts` and `Plans` |
| 3 | `SIZES` `9` / `all priced the same` | `Sizes` `—` / *"This schedule doesn't price connection sizes separately yet."* |
| 4 | `NEXT CHANGE` `01/01/2027` / `+4.0%, filed` | **absent** |
| band | `Revenue` in the absence band | `Revenue` as a fourth **tile**, `—` |

### D2a · ⚠ THE `SIZES` EM-DASH IS A COLUMN THE SERVER SENDS AND THE LIST ALREADY DRAWS

`size_count` is on `ScheduleCard` (`endpoints.ts:3777`) and **the rate-schedules
list renders it**:

`RateSchedulesTab.tsx:317-325`

```tsx
export function sizesText(t: Translator, card: ScheduleCard): string {
  if (card.size_count === 0) return t("rating.rates.sizes.all");
  if (card.size_count === 1) return t("rating.rates.sizes.one");
  return t("rating.rates.sizes.many", { n: card.size_count });
}
```

`rating.rates.sizes.all` = `One rate, every size` · `.many` = `{{n}} sizes`.

**So the list says `9 sizes` and this tile says `—` with a sentence claiming the
schedule does not price sizes separately, from the same object.** That is page 55's
opening complaint word for word: *"the list and this page disagreed about whether
sizes were priced separately."* Verified live.

### D2b · ⚠ `NEXT CHANGE` IS ALSO SERVED AND ALSO DRAWN BY THE LIST

`scheduled_change` is on `ScheduleCard` (`endpoints.ts:3764`) and
`RateSchedulesTab.tsx:668-676` renders it beneath the effective date. The detail
screen never reads it.

### D2c · ⚠ `Accounts` IS ALREADY A COUNT OF **UNITS** — the fix is a label, not a query

`06-backend/apps/rating/selectors.py:1698-1705`

```python
def schedule_applied_to_accounts(tariff: models.Tariff) -> int:
    """Units on a current assignment whose plan attaches this schedule."""
    ...
    return models.UnitPlanAssignment.objects.filter(...).count()
```

The docstring says `Units`; the field is named `applied_to_accounts`; the tile is
labelled `Accounts`. Page 60 gives the reasoning at length — *"A plan is assigned
to a **unit** … The account is billed **because** it occupies the unit, so counting
accounts undercounts by every vacant unit on the schedule, and those vacant units
are exactly the ones whose base charge lands on a landlord's bill."*

**The count is already right and only the words are wrong.** Same for
`PlanRow.accounts`, which is `_plan_accounts_subquery` over `UnitPlanAssignment`
(`selectors.py:369-375`).

## D3 · THE CUSTOMER CLASS IS ON NO PART OF THIS SCREEN — and `account_type_id` is served

`RateScheduleDetail.tsx:697-706` builds the eyebrow from four parts and no class:

```tsx
  const kickerParts = [
    t("rating.rateDetail.kicker.object"),
    detail.service_name,
    enumLabel(translate, "rating.model", detail.structure),
    currentOrdinal === null ? t("…kicker.draft") : t("…kicker.version", { n: currentOrdinal }),
  ].filter(...);
```

and `OverviewTab`'s field grid (`:973-985`) has `Structure` · `Service` ·
`Unit of measure` · `Minimum bill` — no class, and one field the drawing does not
have.

`account_type_id` is on `ScheduleCard` (`endpoints.ts:3761`). `grep account_type_id
RateScheduleDetail.tsx` returns nothing.

## D4 · THE GL ACCOUNT IS CALLED `Revenue account` — the named outlier, verified live

`rating.rateDetail.glLabel` = **`Revenue account`**, read twice: in the sub-line
(`RateScheduleDetail.tsx:947`) and on the Accounting panel (`:1017`).

Page 57: *"This screen said `Revenue account`. Every other screen in the product —
Finance, the ledger, charge codes, taxes, plans, Settings — says `GL account`. One
outlier, now corrected."* This is the RULES line's *"One fact has one wording
everywhere"*, and B14 rule 34's shape one term over.

## D5 · THE RATE TABLE'S LAST COLUMNS ARE `Tier 1 · Tier 2 · Tier 3`, AND THERE IS AN `Accounts` COLUMN

`RateScheduleDetail.tsx:1167-1171`

```tsx
                {Array.from({ length: tierColumns }, (_, index) => (
                  <th key={`t${index}`} scope="col" className={TH}>
                    {t("rating.rateDetail.matrix.col.tier", { seq: index + 1 })}
                  </th>
                ))}
```

`rating.rateDetail.matrix.col.tier` = `Tier {{seq}}`. The drawing wants the block
range. **The strings to build it already exist and are already used by the chart
the drawing removes** — `rating.rateDetail.chart.band` = `{{from}}–{{to}} {{uom}}`
and `.bandOpen` = `{{from}} {{uom}} and above` — which is page 57's own point:
*"which is also what the chart's captions were for, so nothing is lost with it."*

And `MATRIX_COLUMNS` (`:224-229`) carries a fourth fixed column `accounts`,
rendered at `:1198`:

```tsx
                  <td className={`${TD} tabular-nums`}>{props.detail.applied_to_accounts}</td>
```

— **the same schedule-wide total printed on every row**, which is precisely what
the drawn callout forbids: *"All 74 units are counted in the header; nothing counts
units per connection size."*

Header words also differ: `Base` where the drawing says `BASE CHARGE`, and
`Minimum bill` where it says `MINIMUM RATE` (see
`CR-087-p042-create-step2-base-rates.md` D1 for the full rename list).

## D6 · `How it bills` IS DRAWN AS STATED BEHAVIOUR AND BUILT AS THREE EMPTY SETTINGS

`RateScheduleDetail.tsx:1289-1297`

```tsx
          <Field label={t("rating.rateDetail.rules.proration")}>
            <Absent reason={t("rating.rateDetail.rules.notStored")} />
          </Field>
          <Field label={t("rating.rateDetail.rules.rounding")}>
            <Absent reason={t("rating.rateDetail.rules.notStored")} />
          </Field>
          <Field label={t("rating.rateDetail.rules.cap")}>
            <Absent reason={t("rating.rateDetail.rules.notStored")} />
          </Field>
```

`rating.rateDetail.rules.notStored` = *"Not set on a rate schedule yet."*

| drawn | built |
|---|---|
| `PART-PERIOD BILLS` — `Prorated automatically` / `Engine behaviour. There is no setting.` | `Proration` — `—` / *"Not set on a rate schedule yet."* |
| `ROUNDING` — `Two decimals at finalisation` / `One rule for the whole product.` | `Line rounding` — `—` / *"Not set on a rate schedule yet."* |
| `CURRENCY` — `USD` / `The utility's own, in Settings.` | `Currency` — `version?.currency ?? "—"` ✔ |
| `GL ACCOUNT` — `4100-01 — Water revenue` / `Set in Settings, under Accounting.` | on a **separate** `Accounting` panel, labelled `Revenue account` |
| — | `Optional cap` — `—` / *"Not set on a rate schedule yet."*, **not drawn at all** |

**This is the RULES clause `A behaviour is not drawn as an empty setting`, and it
is the single clearest divergence on the screen.** Proration and rounding are not
unset — they are fixed, and B4's rounding rule is ❄️ FROZEN and finance-signed.
Drawing them as blanks invites a clerk to look for the lever.

⚠ **THE VALUES THE DRAWING PUTS THERE ARE SIGNED FIGURES AND MUST BE QUOTED, NOT
RESTATED.** `Two decimals at finalisation` is CLAUDE.md hard rule 2 and B4's
rounding rule; `Prorated automatically` is `rating.rate.prorationNote`'s existing
sentence. **Nothing here proposes changing a signed figure** — it proposes
printing the one that is already signed instead of an em-dash.

## D7 · THE TIER CHART IS STILL RENDERED, AND THERE IS AN EXTRA `Sample bill` PANEL

`RateScheduleDetail.tsx:998-1002` renders `<TierChart …>` on the Overview, which
the drawing removes on a PO instruction. `TierChart` itself is `:1027-1131`.

`RateScheduleDetail.tsx:1005-1012` renders a `Sample bill` panel holding
`rating.rateDetail.sampleBill.unavailable` = *"A worked example is priced by the
billing engine, not by this screen. Run a bill to see one."* The drawing has no
such panel. **The sentence is correct and the panel is not drawn** — the honest
reading is that the absence belongs in a closed `<details>` under B14 rule 32,
not that the statement is wrong.

## D8 · PANEL HEADINGS AND THE POLICY LIST

| drawn | built |
|---|---|
| `What it prices` | `rating.rateDetail.panel.structure` = `Structure` |
| `The rates` | `rating.rateDetail.panel.matrix` = `Rate matrix` (a different TAB) |
| `How it bills` | `rating.rateDetail.panel.howItPrices` = `How it prices` (a different TAB) |
| `What a schedule may and may not do` | `rating.rateDetail.panel.policy` = `Policy` |

Policy list item 1: `rating.rateDetail.rules.oneService` = *"One service per
schedule: this one prices {{service}} and nothing else."* — the drawing adds the
class: *"One service **and one class** per schedule: this one prices Water **for
Residential** and nothing else."* Items 2–4 match verbatim.

Tab explainer: `rating.rateDetail.explainer.overview` = *"What this schedule
prices, and how its rates step up."* → drawn *"What this schedule prices, for
whom, and at what."* (The *"how its rates step up"* clause is the chart's, and
goes with it.)

## D9 · ⚠ FIVE OF ELEVEN CATALOGUES RENDER THIS SCREEN IN ENGLISH

`es-MX`, `hi`, `id-ID`, `ja-JP` and `ko-KR` each carry **88 of the 97
`rating.rateDetail.*` keys byte-identical to `en.json`** — not missing, *identical*
— including `Revenue account`, `Minimum bill`, `Rate matrix`, `Sample bill`,
`Versions & filings` and every full sentence in the STATES and absence copy.
(`rating.rate.*`: 43 of 126 in the same five.) `de`, `es`, `fr-FR`, `it-IT` and
`pt-BR` are translated.

**Every key-parity check passes**, because the keys are all present in all eleven
files. This is B14 rule 35 and it is invisible to the gate that guards it.

## D10 · WHAT IS BUILT AND RIGHT

* **`Duplicate · Edit · Retire`, in that order, Retire in the danger tier** —
  `RateScheduleDetail.tsx:771-836`, and the ruling behind it is quoted in the file
  (`CR-087` E1, PO 2026-09-08). **Matches the drawing exactly.** B14 rule 6 met via
  `variant="danger"`.
* **`← Plans & Rates`** — `rating.rateDetail.back` = `Plans & Rates`, where the
  drawing says `← Rate schedules`. The route it returns to IS the rates tab
  (`RATES_TAB_ROUTE`), so **the label names the wrong destination** under B14 rule
  1 (*"a page header's `←` names where it EXITS to"*). One word.
* **The sub-line's three parts** (`SubLine`, `:911-953`) are the drawn three, in
  the drawn order, with `rating.rateDetail.policyNote` matching verbatim.
* **The UoM-mismatch strip** (`:843-859`) is the drawn `Unit mismatch` state.
* **`rating.rateDetail.noVersion`** = `No version is in force yet` and
  **`rating.rates.noStructure`** = `No pricing entered yet.` — both drawn states,
  both built, both verbatim.
* **The KPI strip renders outside the tab switch** (`:833`), so the tiles appear
  on all tabs, which is what the drawing shows on 18, 19 and 20.

---

## ABSENCES — drawn as absent, do not fill them

* **No chart** (D7).
* **No `Accounts` column on the rate table** (D5).
* **No worked sample bill.**
* **No `Optional cap` field.**
* **No inline editing of the matrix** — `Edit` opens the five-step wizard and
  writes a new version. The code already refuses a second write path and says why
  (`RateScheduleDetail.tsx` lifecycle, exception E2).

---

## CONTRADICTIONS AND THINGS FOR THE PRODUCT OWNER

1. **THE `SIZES` TILE'S TWO SENTENCES ARE BOTH IN THE PRODUCT AND THEY DISAGREE
   (D2a).** This is not a drawing-versus-code question — the list and the detail
   contradict each other today, from one served field. Whatever is decided about
   the other three tiles, this one is a live inconsistency.

2. **`How it bills` PUTS SIGNED FIGURES ON A SCREEN (D6).** `Two decimals at
   finalisation` is B4, ❄️ FROZEN. Printing it is right; **wording it in a way that
   diverges from B4's own sentence would create a second statement of a signed
   rule.** The wording should be lifted from B4, not composed.

3. **THE `← Rate schedules` LABEL.** The drawing says `Rate schedules`; the code
   says `Plans & Rates` and navigates to the rates tab. B14 rule 1 wants the label
   to name the destination, which makes the drawing right — but `Plans & Rates` is
   also the module name a clerk sees in the nav. **One sentence to the PO.**

4. **`NEXT CHANGE`'s DETAIL LINE (`+4.0%, filed`) NEEDS A PERCENTAGE NOBODY
   SERVES ON THE CARD.** `scheduled_change` is a DATE (`endpoints.ts:3764`). The
   `+4.0%` would have to come from the impact endpoint or be computed — and
   computing it is B4 arithmetic in a component. **Recorded; the date half is free,
   the percentage half is not.**

---

## ⚑ BUILT 2026-09-10 — `CR-087` RATE-SCHEDULE MAINTENANCE LANE

**D2 · THE FOUR DRAWN TILES ARE BUILT** — `In force` · `Units` · `Sizes` ·
`Next change` — and `Revenue` moves to an absence band beneath them, because an
em-dash standing in a row of live figures reads as ZERO.

**D2a · THE LIST AND THIS PAGE CAN NO LONGER DISAGREE.** Both call `sizesText`,
the list's own function, over the same `size_count`. The sentence claiming the
schedule does not price sizes separately is retired from all eleven catalogues.
⚠ **The drawn `9 / all priced the same` is NOT what is rendered**: that needs a
count of the SERVICE's size classes, which no endpoint serves on this object.
What is rendered is the list's wording, from one source. **Divergence recorded.**

**D2b · `NEXT CHANGE` READS `scheduled_change`.** The `+4.0%` half of its detail
line is not built — contradiction 4 of this file is right that it would be B4
arithmetic in a component.

**D2c · `Accounts` → `Units`, A RENAME AND NOT A QUERY CHANGE.** The count was
always `UnitPlanAssignment` rows. The wire field keeps its name.
⚠ **A THIRD SURFACE IS STILL WRONG:** `PlansTab.tsx`'s own list column reads
`rating.plans.col.accounts` over the same subquery. Not touched — it is another
screen, and §3 of the maintenance process says file it rather than widen.

**D3 · THE CUSTOMER CLASS IS ON THE SCREEN** — the eyebrow's third part and a
field of its own, resolved to a NAME through the platform list (B14 rule 31). A
schedule with none says `Every customer class`; the eyebrow simply drops it.

**D4 · `Revenue account` → `GL account`**, in all eleven catalogues.

**D5, D6, D7, D8 · NOT DONE.** The rate table still says `Tier 1 · Tier 2`, still
carries the `Accounts` column, `How it bills` is still three stated absences, the
tier chart is still rendered and the panel headings are unchanged. Each needs
layout work this lane did not reach; **D6 in particular puts ❄️ FROZEN B4 wording
on a screen and must quote B4 rather than compose a sentence.**
**D9 · FILED, NOT SWEPT** — see the defect register for the five English
catalogues; the keys this lane touched were translated properly.
