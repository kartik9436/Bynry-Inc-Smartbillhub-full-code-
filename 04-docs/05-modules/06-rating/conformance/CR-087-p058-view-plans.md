# 19 · Rate schedule → View · Plans — THE DRAWN SPEC

`S11 · RAT-02` · route `/:tenant/plans-rates/rates/:id?tab=plans` · **blueprint pages 58–61**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section opening
at the foot of page 58, **frame drawn on page 59**, specified on 60–61. Read as
RENDERED pages — the five-column table, the status pills and the closing callout
are only in order as a picture.

**State chip:** `EXISTS BEHIND`
**Commitment:** `NO COMMITMENT` — nothing in section 03 undertakes this screen.

**Masthead warning, applied.** As-built at **2.232.0**; re-checked at **2.234.19**.

---

## 1 · Header, actions, tabs, tiles — identical to screen 18

`← Rate schedules` · eyebrow `RATE SCHEDULE · WATER · RESIDENTIAL · TIERED · V3` ·
title `Sample — Residential water (inclining tiers)` · `ACTIVE` pill · sub-line
*"In force from 06/01/2026 · GL account 4100-01 — Water revenue · Rate changes save
as a new version; a version in force is never edited."* · actions
`Duplicate` `Edit` `Retire` · tabs `Overview | Plans | Audit` with **`Plans`
active** · the four tiles `IN FORCE` `UNITS` `SIZES` `NEXT CHANGE` and the
`NOT WORKED OUT YET · Revenue` absence band.

**Tab explainer, one sentence:**
`The plans that carry this schedule to customers.`

## 2 · The panel — `Plans using this schedule`

**Heading:** `Plans using this schedule` · no hint line.

| # | header | alignment | content |
|---|---|---|---|
| 1 | `PLAN` | left | `Sample — Residential` · `Sample — Commercial` · `Sample — Industrial` |
| 2 | `CODE` | left | `SCW-RES` · `SCW-COM` · `SCW-IND` |
| 3 | `CLASS` | left | `Residential` on every drawn row |
| 4 | `STATUS` | left, **a pill** | `PUBLISHED` · `PUBLISHED` · `DRAFT` |
| 5 | `UNITS` | left, numeric | `74` · `12` · `0` |

⚠ **B14 rule 37 — every plan name, code and figure above is an ILLUSTRATION.** The
shape is five columns, a status pill, and a count that is UNITS.

⚠ **THE `CLASS` COLUMN IS THE REASON THE TAB IS WORTH OPENING.** Page 60: *"New,
and it is the reason this tab is worth opening now. A schedule prices one class; a
plan targets one class. Where the two differ, customers are billed by a formula
written for somebody else — the plan builder already warns about it and this was
the one screen that could show it across every plan at once."*

## 3 · Closing callout, accent

| legend | sentence |
|---|---|
| `WHEN A CLASS DOES NOT MATCH` | `A plan whose class differs from this schedule's is named here, because bills priced by it may not match what those customers were offered.` |

## 4 · States — verbatim

| state | drawn behaviour |
|---|---|
| **Nothing carries it** | *"`No plan carries this rate schedule yet.` A schedule with no plan prices nobody."* |
| **A draft plan carries it** | *"Listed, 0 units, Draft pill — it reaches nobody and the row shows why."* |
| **A class mismatch** | *"The row is marked and the note above explains the consequence."* |

## 5 · Components named in the frame

`Panel` `ListTable` `StatusPill` `Callout accent`

## 6 · FOR · HOW YOU GET HERE · PRIMARY ACTION

* **FOR** — *"A clerk about to change prices, checking what a change reaches."*
* **HOW YOU GET HERE** — *"The `Plans` tab."*
* **PRIMARY ACTION** — **`None.`**
* **RULES, extra clause** — *"Two surfaces showing one fact read it from one source."*

---

# THE DIFF — drawing against the code at 2.234.19

Code: `RateScheduleDetail.tsx` — `PlansTabPanel` at line **1320**.

## D1 · THE `CLASS` COLUMN IS MISSING — and the field it needs is served on every row

`RateScheduleDetail.tsx:1340-1354` declares four headers:

| # | drawn | built | key |
|---|---|---|---|
| 1 | `PLAN` | `Plan` | `rating.plans.col.plan` |
| 2 | `CODE` | `Code` | `rating.plans.col.code` |
| 3 | `CLASS` | **absent** | — |
| 4 | `STATUS` | `Status` | `rating.plans.col.status` |
| 5 | `UNITS` | `Accounts` | `rating.plans.col.accounts` |

`PlanRow.account_type_id` is served (`07-frontend/src/api/endpoints.ts:3103`) and
the plan detail already reads it twice (`PlanDetail.tsx:905`, `:1238`). **The
column the drawing adds is a column the server already sends.**

To render a NAME rather than an id, the class lookup is
`getLookupEntries`/`account_types` (`06-backend/apps/customers/lookups.py:441`) —
the same list the plan wizard's class picker uses
(`PlanWizard.tsx:2149-2155`). **B14 rule 31 — no database id is ever the visible
value of a field** — so the id alone is not enough and the lookup is part of the
work.

## D2 · THE COMPARISON THE COLUMN EXISTS FOR IS NOT MADE

Nothing on this tab compares a plan's class with the schedule's. There is no
mismatch mark on a row and no `WHEN A CLASS DOES NOT MATCH` callout.

⚠ **THE SCHEDULE'S HALF OF THE COMPARISON IS ALSO UNREAD** — see
`CR-087-p055-view-overview.md` D3: `account_type_id` is never read on this screen.
So the mismatch cannot be computed today even though both operands are on the
wire.

**The plan builder already does this comparison**, which is what page 60 means by
*"the plan builder already warns about it"*: `PlanWizard.tsx:1079-1083` filters
schedules whose `account_type_id` is set and differs from the draft plan's.

## D3 · `Accounts` SHOULD READ `Units`, AND THE FIGURE IS ALREADY UNITS

`RateScheduleDetail.tsx:1361` renders `{plan.accounts}` under a header labelled
`Accounts`.

`06-backend/apps/rating/selectors.py:369-375`

```python
def _plan_accounts_subquery() -> Subquery:
    return Subquery(
        models.UnitPlanAssignment.objects.filter(rate_plan=OuterRef("pk"), assigned_to__isnull=True)
        .values("rate_plan")
        .annotate(total=Count("id"))
        .values("total")[:1]
    )
```

**It counts current unit-plan assignments.** The number is already what the
drawing asks for; the wire name (`accounts`), the sort key (`selectors.py:406`)
and the column label are what say otherwise. Same story as the header tile — see
`CR-087-p055-view-overview.md` D2c.

## D4 · THE TILE AND THE TABLE COME FROM TWO DIFFERENT READS — the named defect, verified live

| surface | source |
|---|---|
| the `UNITS`/`Accounts` and `Plans` tiles | `detail.applied_to_accounts` / `detail.used_by_plans` — `GET /rate-schedules/{id}` |
| this table | `getPlans({ per: 200 })` — `GET /plans`, filtered **in the browser** |

`RateScheduleDetail.tsx:598-601`

```tsx
  const plansQuery = useQuery({
    …
    queryFn: () => getPlans({ per: PLAN_SCAN_PER }, client),
```

`RateScheduleDetail.tsx:491-495` — `plansUsingSchedule` filters the page by
`plan.rate_schedules[].tariff_id`.

The file states the reason honestly at `:483-489`: *"`GET /plans` declares no
`tariff` filter (`PLAN_FILTERS` is status · service · customer_class) and BR-SHL-011
IGNORES an undeclared filter rather than refusing it — so asking for one would
silently return every plan looking like a filtered list."* Confirmed:
`06-backend/apps/rating/selectors.py:100` —
`PLAN_FILTERS: tuple[str, ...] = ("status", "service", "customer_class")`.

Page 60: *"The header tile and this table came from two different reads and could
disagree, under a note that counted every plan in the utility rather than the
plans carrying this schedule. **One server answer serves both.**" That needs a
`tariff` filter on `GET /plans`, or a plans list on the schedule endpoint. **Server
work, named here rather than assumed.**

## D5 · ⚠ THE 200-ROW SCAN IS AN `NFR-3` HAZARD AND ITS COMMENT NAMES THE RETIRED CEILING

`RateScheduleDetail.tsx:497-499`

```tsx
/** One of IS-2's clamped page sizes (PO ruling 2026-08-09), the largest that is
 *  still one request. A tenant under 3,000 connections has tens of plans. */
const PLAN_SCAN_PER = 200;
```

**`3,000` is the ceiling CLAUDE.md moved to `40,000` on 2026-09-06.** The scan is
bounded, the screen says so when it truncates
(`rating.rateDetail.plans.truncated` = *"Checked the first {{shown}} plans of
{{total}}. A plan beyond that is not listed here."*) — so it fails honestly rather
than silently, which is better than the four `NFR-3` breaches CLAUDE.md names. But
it is the same shape: a client-side page justified by the old ICP.

**Fixing D4 fixes this too** — a `tariff` filter makes the read exact instead of a
scan. Recorded as a second reason to do it, not as a separate defect.

## D6 · THE TABLE IS A RAW `<table>`, NOT A KIT TABLE

`RateScheduleDetail.tsx:1338-1370` writes its own `<thead>`/`<tbody>` with the
file-local `TH`/`TD` class strings (`:512-517`). The kit has `DataTable`
(toolbar, column chooser, pagination footer) and `PlainTable`
(`components/Surfaces.tsx:96`).

⚠ **THE DRAWING DRAWS NO TOOLBAR AND NO FOOTER**, so `DataTable` is NOT what the
drawing asks for, and **B14 rule 16's *"pagination footer on every list table"*
points the other way.** Under B14 rule 38 this is construction and the UI rules
win — but rule 16's own exemption is for *wizard summary tables*, which this is
not. **The honest resolution is `PlainTable` (the kit's un-chromed table) rather
than a bespoke one**, which satisfies rule 36 (*compose the kit*) without adding
chrome the drawing does not want. **Recorded as a divergence, not a defect** —
and the same question applies to the Audit tab.

## D7 · `STATUS` IS A WORD, NOT A PILL

`RateScheduleDetail.tsx:1360` renders
`{enumLabel(translate, "rating.plan.status", plan.status)}` — plain text — where
the drawing draws a bordered pill (`PUBLISHED` green, `DRAFT` grey), and the
frame's own COMPONENTS line names `StatusPill`. The component exists
(`components/StatusPill.tsx`) and this same file already uses its rating wrapper
for the header and the version table (`RatingStatusPill`).

## D8 · WHAT IS BUILT AND RIGHT

* **`rating.rateDetail.panel.plans`** = `Plans using this schedule` — **verbatim**.
* **`rating.rateDetail.plans.empty`** = `No plan carries this rate schedule yet.` —
  **verbatim**, and it is the drawn `Nothing carries it` state.
* **`rating.rateDetail.explainer.plans`** = `The plans that carry this schedule to
  customers.` — **verbatim**.
* **No primary action on this tab** — matches `PRIMARY ACTION · None.`
* **A loading state** — `LoadingSkeleton variant="table"` (`:1333`), which the
  drawing does not draw and which every data element needs.

## D9 · ⚠ FIVE CATALOGUES RENDER THIS TAB IN ENGLISH

The same 88-of-97 English-identical `rating.rateDetail.*` block described in
`CR-087-p055-view-overview.md` D9 covers this tab's panel heading, explainer,
empty state and truncation note in `es-MX`, `hi`, `id-ID`, `ja-JP` and `ko-KR`.

---

## ABSENCES — drawn as absent, do not fill them

* **No action column.** No `Open plan`, no row actions, no icons.
* **No toolbar, no filters, no column chooser, no pagination footer.**
* **No hint line under the panel heading.**
* **No effective dates, no base charge, no services column** — this table answers
  one question.

---

## CONTRADICTIONS AND THINGS FOR THE PRODUCT OWNER

1. **`UNITS` REQUIRES RENAMING A SERVED FIELD (D3).** `PlanRow.accounts` is on the
   public shape and is read by more than this screen. Renaming the wire field is a
   contract change; renaming only the LABEL is a one-line change that makes the
   screen right and leaves the wire lying. **The blueprint asks for the words to
   be true; which layer they change at is a call to make once, for the tile and
   this column together.**

2. **B14 RULE 16 VERSUS THE DRAWN FOOTERLESS TABLE (D6).** Two list tables in this
   section (this one and Audit) are drawn with no pagination footer. Rule 16 says
   every list table carries one. **One sentence to the PO, covering both tabs.**

3. **THE CLASS MISMATCH IS A BILLING-CORRECTNESS SIGNAL, NOT A COSMETIC COLUMN.**
   Page 60: *"customers are billed by a formula written for somebody else."*
   Whatever priority the rest of this tab gets, that sentence is worth showing the
   PO on its own.

---

## ⚑ BUILT 2026-09-10 — `CR-087` RATE-SCHEDULE MAINTENANCE LANE

**D1 · THE `CLASS` COLUMN IS BUILT**, resolved to a NAME through the same
platform list the plan builder's picker uses (B14 rule 31 — never the id).

**D2 · THE COMPARISON IS MADE.** `planClassMismatch` marks a row whose class
differs from the schedule's and the `WHEN A CLASS DOES NOT MATCH` callout appears
only when one does. ⚠ **A `null` on EITHER side is NOT a mismatch** — a schedule
with no class prices every class and a plan with no class takes whatever prices
it — so the test is on the ids, and the case that pins it is in the suite.

**D3 · `Accounts` → `Units`** — the figure is unchanged; see `p055` D2c.

**D6 · `PlainTable`, THE KIT'S UN-CHROMED TABLE.** The drawing draws no toolbar
and no footer, so `DataTable` is the wrong piece and a hand-rolled `<table>` is
B14 rule 36's complaint. ⚠ **The divergence from B14 rule 16 (*a pagination
footer on every list table*) is RECORDED and not resolved** — rule 16's own
exemption is for wizard summary tables and this is not one. Contradiction 2 of
this file still needs the PO, for this tab and the Audit tab together.

**D7 · `STATUS` IS A PILL**, the same `RatingStatusPill` the version table uses.

**D4, D5 · NOT DONE.** The tile and the table still come from two different reads
and the 200-row client scan stands; both need a `tariff` filter on `GET /plans`,
which is server work this lane did not take. ⚠ The scan's comment still names the
retired 3,000-connection ceiling.
