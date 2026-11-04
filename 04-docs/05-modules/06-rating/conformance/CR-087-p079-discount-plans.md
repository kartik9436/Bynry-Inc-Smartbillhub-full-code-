# CHG-01.discount · View · Plans — THE DRAWN SPEC, AND WHAT IS BUILT

Blueprint screen **27**, `/:tenant/plans-rates/discounts/:id?tab=plans` ·
**blueprint pages 79–81**, frame drawn on **pages 79–80**.

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`
(md5 `2e46f5053ca65804da9c1a90a487e044`), text **and** rendered PNGs at 2.0.

**State chip:** `EXISTS BEHIND` · **Commitments:** `NO COMMITMENT`

⚠ **`EXISTS BEHIND` MEANS THE SCREEN IS DRAWN AND THE DATA BEHIND IT IS
SERVED.** The blueprint is claiming this table can be built from reads that
exist. §1 below tests that claim against the code and it does not hold.

**Re-verified at 2.234.19** (blueprint read at 2.232.0 / d2d493e4).

**Code read:** `DefinitionDetailPage.tsx` — `DefinitionTabBody`, **679–770**;
`definitionDetail.tsx` — `PLANS_TAB`, **145**.

---

## 1 · Header — unchanged from screen 26

Back link `← Discounts` · kicker `DISCOUNT · SENIOR · PERCENTAGE · V2` · title
`Senior citizen discount` · pill `ACTIVE` · the two-part sub-line ·
`Duplicate` `Edit` `Retire` (`Retire` in the danger tier).

## 2 · Tabs — `Plans` active

`Overview` | **`Plans`** | `Audit`

## 3 · Tab intro line

> `Where this discount is offered, and how many took it.`

## 4 · KPI strip and absence bar — drawn again, unchanged

The same four tiles (`VALUE` · `ENROLLED UNITS` · `BUDGET REMAINING` ·
`STATUS`) and the same `NOT WORKED OUT YET / Programme cost per month` bar as
screen 26. **The strip and the bar are page furniture, present on all three
tabs.**

## 5 · The one panel — `Where this is offered`

**A four-column table.**

| # | header | alignment |
|---|---|---|
| 1 | `PLAN` | left |
| 2 | `OFFERED` | left |
| 3 | `ELIGIBLE UNITS` | left *(numeric, drawn left)* |
| 4 | `ENROLLED` | left *(numeric, drawn left)* |

**The two drawn rows:**

| `PLAN` | `OFFERED` | `ELIGIBLE UNITS` | `ENROLLED` |
|---|---|---|---|
| `Sample — Residential` | `Whenever the discount is available` | `74` | `28` |
| `Sample — Commercial` | `From 01/01/2026` | `12` | `3` |

## 6 · The callout, below the table, inside the panel

Label `OFFERED, NOT GIVEN`, accent left rule, body verbatim:

> `Attaching a discount to a plan makes it available. It reduces nobody's bill`
> `until an account is enrolled — which is why the last two columns are different`
> `numbers.`

⚠ **WHY THE TAB IS WORTH OPENING.** Page 80: *"It names them, and adds the
comparison that makes it worth opening: how many could have it against how many
took it. Twenty-eight of seventy-four is the sentence a programme owner came
for."*

## 7 · Footer

**None drawn.** No pagination, no totals. **PRIMARY ACTION:** `None.`

## 8 · States — verbatim

| state | drawn behaviour |
|---|---|
| **Offered nowhere** | *"No plan offers this discount, so nobody can enrol."* |
| **Offered within a window** | *"The plan's own window is shown, which can be narrower than the discount's."* |

## 9 · Components named by the drawing

`Panel` `ReachTable` `Callout accent`

## 10 · Rules, verbatim — one clause more than screen 26

*"… A figure that does not exist is stated with its reason and never drawn at
the weight of one that does. **A count names what it counts.**"*

## 11 · Absences — drawn as absent

* **No toolbar** — no search, no filter chips, no column selector.
* **No pagination footer.**
* **No row actions.**
* **No link from a plan name.**

⚠ **THE ABSENCE OF A TOOLBAR AND A PAGINATION FOOTER IS CONSISTENT WITH B14
RULE 16's OWN EXEMPTION SHAPE**, not with rule 12 and rule 16 as written for a
LIST table. A discount is offered on a handful of plans, and the drawing draws a
panel table rather than a `DataTable`. Recorded so a lane does not add a toolbar
the drawing does not want — **and so nobody reads it as a licence to build an
unpaginated list**: `NFR-3` (universal server pagination) and `NFR-5` (no hard
caps) are about tenant-scale lists, and this is a per-object fact table whose row
count is the number of plans carrying one discount.

---

## AS BUILT AT 2.234.19 — the diff, with evidence

### Matches

* The tab exists, is second in the strip, and is reachable at
  `?tab=plans` — `definitionDetail.tsx:85`, `:145`.
* The header, the strip and the tab are shared with screen 26 and render on this
  tab too — `DefinitionDetailPage.tsx:605` puts `KPIStrip` above the tab body.

### 1 · THE TABLE IS NOT BUILT. THE TAB IS ONE SENTENCE ABOUT ITS OWN ABSENCE

`DefinitionDetailPage.tsx:722-726`:

```
if (props.tab === PLANS_TAB) {
  // The KPI tile says HOW MANY plans carry it (`used_by_plans`, served). WHICH
  // plans is a different read and no route answers it.
  return <ArrivesWith title={heading} message={t("rating.definition.plans.arrivesWith")} />;
}
```

renders *"The tile above counts the plans that carry this definition. Naming
them one by one needs a read that does not exist yet."*

That is, precisely, the blueprint's own *"What was wrong"* for this screen:
**"The tab rendered a sentence saying it could not name what it exists to
name."** Unchanged at 2.234.19.

⚠ **AND THE `EXISTS BEHIND` CHIP IS WRONG FOR THREE OF THE FOUR COLUMNS.**

| drawn column | is the read there? |
|---|---|
| `PLAN` | **No.** No endpoint lists the plans carrying one discount. The tile counts them (`row.plans`, `definitionDetail.tsx:948`); nothing names them. |
| `OFFERED` | **No.** `plan_discount_rules` carries the per-plan window (`BR-RAT-069`), and no read serves it to this screen. |
| `ELIGIBLE UNITS` | **No — and this is `PRB-20`, which is UNVERIFIED.** `PRB-20`'s own card says *"Nothing in the product works out eligibility"* and names screens `26 · 37`. Column 3 is that number, per plan. |
| `ENROLLED` | **Partly.** `row.enrolled` is served for the discount as a whole (`:950`); per plan it is not. |

**So the state chip and the commitment cards disagree** — see CONTRADICTIONS §1.

### 2 · The callout is not built, and there is no kit component behind it either

`OFFERED, NOT GIVEN` states `BR-RAT-069` — AVAILABLE ≠ GRANTED — at the one
place two numbers sit side by side inviting the wrong reading. Nothing renders
it. `components/ConsequenceBox.tsx`'s staff shape (`tag` + `title` + one-sentence
`body`) is the kit's answer; see the root-cause note in `CR-087-p074` §4.

### 3 · The tab intro sentence is not built

`PageHeader` has no slot for one (`components/PageHeader.tsx:115-213`). Same gap
as screens 26 and 28.

### 4 · The absence bar is not built on this tab either

Drawn between the strip and the panel on all three tabs. Built only as the
`Who qualifies` block note on the **Overview** — so on `Plans` it is absent
entirely. See `CR-087-p076` §2.

---

## CONTRADICTIONS INSIDE THE BLUEPRINT — recorded, not resolved

1. **`EXISTS BEHIND` AGAINST `PRB-20`.** The chip asserts the data behind this
   screen is served; column 3 (`ELIGIBLE UNITS`) is exactly the figure `PRB-20`
   says nothing in the product works out, and columns 1, 2 and 4 need a per-plan
   read that no route answers. **Reading: the chip is optimistic and the
   commitment card is the accurate half** — `PRB-20`'s card is dated and
   specific, the chip is a one-word badge. Recorded, because a lane reading the
   chip alone would plan this tab as a rendering job and find four missing
   reads.

2. **`ELIGIBLE UNITS` IS THE SAME WORD PROBLEM AS SCREEN 26's TILE 2.** The
   drawn column heads `ELIGIBLE UNITS` beside `ENROLLED` — units against
   accounts, in adjacent columns, under a RULES line that says *"a count names
   what it counts"*. `definitionDetail.tsx:955-966` argues the two populations
   must not be drawn as one fraction. Same question, second surface. See
   `CR-087-p076` §1(a).

---

## WHAT NEEDS THE PRODUCT OWNER

* Nothing new here that `CR-087-p076` does not already raise. The two carried
  forward: **units against accounts in adjacent columns**, and **whether this
  tab is scheduled at all**, given that its four columns need reads nobody has
  committed to (only `PRB-20` is even named, and it is `UNVERIFIED`).

## WHAT COULD NOT BE VERIFIED WITHOUT THE APP RUNNING

* Nothing on this tab renders but one sentence, so both drawn STATES
  (`Offered nowhere`, `Offered within a window`) are unreachable and untested by
  construction.
