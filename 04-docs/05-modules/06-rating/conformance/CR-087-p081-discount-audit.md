# CHG-01.discount · View · Audit — THE DRAWN SPEC, AND WHAT IS BUILT

Blueprint screen **28**, `/:tenant/plans-rates/discounts/:id?tab=audit` ·
**blueprint pages 81–83**, frame drawn on **pages 81–82**.

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`
(md5 `2e46f5053ca65804da9c1a90a487e044`), text **and** rendered PNGs at 2.0.

**State chip:** `EXISTS BEHIND` · **Commitments:** `NO COMMITMENT`

**Re-verified at 2.234.19** (blueprint read at 2.232.0 / d2d493e4).

**Code read:** `DefinitionDetailPage.tsx` — `DefinitionTabBody`, **679–770**;
`DatedBanner`, **771–782**; `definitionDetail.tsx` — `VERSIONS_TAB` /
`AUDIT_TAB` / `isHistoryTab`, **127–143**.

---

## 1 · Header — unchanged from screen 26

Back link `← Discounts` · kicker `DISCOUNT · SENIOR · PERCENTAGE · V2` · title
`Senior citizen discount` · pill `ACTIVE` · the two-part sub-line ·
`Duplicate` `Edit` `Retire` (`Retire` in the danger tier).

## 2 · Tabs — `Audit` active

`Overview` | `Plans` | **`Audit`**

⚠ **THE TAB IS CALLED `Audit`, NOT `Versions`.** Page 82: *"The name follows the
product's own word, as on the rate schedule and the charge code."*

## 3 · Tab intro line

> `What it has been worth, and who changed it.`

## 4 · KPI strip and absence bar — drawn again, unchanged

The same four tiles and the same `NOT WORKED OUT YET / Programme cost per month`
bar as screens 26 and 27.

## 5 · The one panel — heading `Audit`

**A six-column table.**

| # | header |
|---|---|
| 1 | `VERSION` |
| 2 | `EFFECTIVE` |
| 3 | `VALUE` |
| 4 | `WHY IT CHANGED` |
| 5 | `BY` |
| 6 | `STATUS` |

**The two drawn rows, newest first:**

| `VERSION` | `EFFECTIVE` | `VALUE` | `WHY IT CHANGED` | `BY` | `STATUS` |
|---|---|---|---|---|---|
| `v2` | `01/01/2026 →` | `10%` | `Raised from 5% after the 2026 assistance review` | `Dana Whitfield` | `ACTIVE` *(pill, positive tone)* |
| `v1` | `01/01/2025 – 12/31/2025` | `5%` | `First version` | `Dana Whitfield` | `SUPERSEDED` *(pill, neutral tone)* |

⚠ **AN OPEN-ENDED RANGE IS `01/01/2026 →`; A CLOSED ONE IS `01/01/2025 –
12/31/2025`.** Two shapes in one column, and the arrow is what says *still
running*.

## 6 · The callout, below the table, inside the panel

Label `DATED`, accent left rule, body verbatim, **two sentences**:

> `A version prices from its own effective date. A bill already issued is never`
> `re-priced.`

## 7 · Footer

**None drawn.** **PRIMARY ACTION:** `Edit`, *"from the header, which drafts the
next version."*

## 8 · States — verbatim

| state | drawn behaviour |
|---|---|
| **One version** | *"`First version`, and no comparison to draw."* |
| **A draft version** | *"Listed above the active one, marked Draft, with a note that a draft prices nothing and enrols nobody."* |

## 9 · Components named by the drawing

`Panel` `VersionTable` `StatusPill` `Callout dated`

## 10 · Rules, verbatim

*"… A figure that does not exist is stated with its reason and never drawn at
the weight of one that does."*

## 11 · Absences — drawn as absent

* **No toolbar, no pagination, no row actions, no diff link.**
* **No `audit_log` rows.** Page 82 and the code agree: this is the object's own
  version table, not a filtered actor/action/timestamp log.

---

## AS BUILT AT 2.234.19 — the diff, with evidence

### Matches

* **The tab is named `Audit`** and is third in the strip —
  `definitionDetail.tsx:85`, `AUDIT_TAB` at `:134`. **The rename is done.**
* **`isHistoryTab` knows both spellings** while the charge and the tax still say
  `versions` — `:140-142`. The migration is honest and in one place.
* **The `DATED` callout is built** — `DefinitionDetailPage.tsx:771-782`, a
  left-accent-ruled `<section role="note">` with a `Kicker` label and a `Note`
  body, rendered on every history tab (`:714-720`). **The drawn shape is
  matched.**
* **`Edit` is the primary action and drafts a new dated version** —
  `DefinitionDetailPage.tsx:548-570`, routing to
  `definitionWizardPath(kind, id)`; `BR-RAT-078` is why there is no
  `PATCH /discounts/{id}`.

### 1 · THE VERSION TABLE IS NOT BUILT. THE TAB IS ONE SENTENCE ABOUT ITS OWN ABSENCE

`DefinitionDetailPage.tsx:710-721`:

```
if (isHistoryTab(props.tab)) {
  return (
    <>
      <ArrivesWith title={heading} message={t("rating.definition.versions.arrivesWith")} />
      <DatedBanner t={t} />
    </>
  );
}
```

renders *"This tab lists the object's own version history — what the price was,
from when, and the reason someone wrote for the change. It is not the audit log,
and no endpoint serves those versions yet."*

That is the blueprint's own *"What was wrong"*: **"The tab rendered a sentence
about its own absence, under a name no other module uses."** The **name** half
was fixed by `CR-087` C2. The **sentence** half is unchanged at 2.234.19.

⚠ **AND THE `EXISTS BEHIND` CHIP IS THE MOST DEFENSIBLE OF THE THREE VIEW
SCREENS, BUT IT IS STILL NOT TRUE TODAY.** `discount_versions` is a real table
and every drawn column has a column behind it — page 82 is right that this
object's history is *"closest to working — this wizard already required a reason
and already stored it"*. What is missing is the **read**: no route lists a
discount's versions. `GET /discounts/{id}` serves `version_no`,
`version_status`, `version_id` and `value_display` for **the one version in
force** (`definitionDetail.tsx:924-970`, `DefinitionDetailPage.tsx:566-572`) and
no history.

### 2 · The `DATED` body is a different sentence

| drawn | built | evidence |
|---|---|---|
| `A version prices from its own effective date. A bill already issued is never re-priced.` | `Bills always use the version in force on the usage date.` | `rating.definition.dated.body` |

Both are true; they say different halves of the rule. The drawn pair says
**where a price comes from** and **that an issued bill is immutable** — the
second is `CLAUDE.md` hard rule 4 in a clerk's words, and it is the half the
built sentence omits.

⚠ **THE STRING IS SHARED WITH THE CHARGE AND THE TAX KINDS** (`DatedBanner` is
rendered by `isHistoryTab` for all three, `DefinitionDetailPage.tsx:714`), so
rewording it moves three screens. Recorded, not proposed.

### 3 · `DatedBanner` is a fourth hand-rolled callout

`:773-777` is a bespoke `<section className="border-l-2 border-l-accent
bg-surface p-3 mb-4 max-w-measure">`. `components/ConsequenceBox.tsx` is the
kit's staff callout and takes exactly this shape. See the root-cause note in
`CR-087-p074` §4 — this is the fourth of four spellings in pages 65–84.

### 4 · The tab intro sentence is not built

Same gap as screens 26 and 27 — `PageHeader` has no slot
(`components/PageHeader.tsx:115-213`).

### 5 · The absence bar is not built on this tab either

See `CR-087-p076` §2.

### 6 · `STATUS` needs a version-level status vocabulary the screen does not have

The drawn pills are `ACTIVE` and `SUPERSEDED` — **version** statuses. The
catalogue's `rating.discounts.status.*` is the **discount's** four
(`active · draft · retired · suspended_funding_exhausted`) and carries no
`superseded`. `discountLifecycleActs` reads a `version_status` that includes
`superseded` (`DiscountLifecycle.test.tsx:126`), so the value exists on the wire
with no label in any of the eleven catalogues. **Building the drawn column needs
a version-status label set.** Recorded.

---

## CONTRADICTIONS INSIDE THE BLUEPRINT — recorded, not resolved

1. **`EXISTS BEHIND` AGAINST `NO COMMITMENT`.** The chip says the data is
   served; no commitment card in section 04 undertakes the version-list read.
   So the blueprint asserts the tab is buildable and undertakes nothing to build
   it. **Reading: the chip describes the TABLES, not the ROUTES** — which is
   consistent with page 82's *"closest to working"* wording and with the
   `NEW READ` chip existing as a separate state for *"the screen exists and
   something on it has no read"*. On that reading this screen is mis-chipped and
   should be `NEW READ`. Recorded; the PO owns the chip vocabulary.

2. **THE DRAWN DATES ARE `MM/DD/YYYY` AND THE MODULE IS ON A TENANT FORMAT.**
   `01/01/2026`, `12/31/2025`. `BR-SHL-033` / `IS-8` put every date in this
   module through the tenant's own format (`useRegional`, used on this very page
   at `DefinitionDetailPage.tsx` for `dateNode`). **B14 rule 37 makes a drawn
   figure an illustration, and a date is a figure** — so the drawn slashes are
   an example of a shape, not a format to build to. Recorded so no lane pins a
   test to `01/01/2026`.

---

## WHAT NEEDS THE PRODUCT OWNER

* **CONTRADICTIONS §1** — whether this tab is scheduled. It carries
  `EXISTS BEHIND` and `NO COMMITMENT`, which together mean nobody has undertaken
  it, and the tab is the screen a regulator's assistance filing is answered from
  (page 82's `FOR`).
* **§2** — the `DATED` sentence is shared with the charge and the tax; changing
  it to the drawn pair moves three screens.

## WHAT COULD NOT BE VERIFIED WITHOUT THE APP RUNNING

* Both drawn STATES (`One version`, `A draft version`) are unreachable — the tab
  renders one sentence.
* Whether the `DATED` banner's left rule and the drawn callout's left rule are
  the same token.
