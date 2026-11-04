# 12 · View · Audit — THE DRAWN SPEC, AND WHAT THE PRODUCT DOES

`S13` · route `/:tenant/plans-rates/taxes-fees/:id?tab=audit` · **blueprint pages
36–38** (heading on 36, frame drawn on **36–37**, specified on 37–38).

**State chip:** `EXISTS BEHIND` **Commitment:** `NO COMMITMENT`

⚠ **THE CHIP AND THE PROSE DISAGREE — SEE §7**, the same way they do on screen 11.

**Re-verify:** as-built claims were true at **2.232.0**; we are on **2.234.19**.

---

## 1 · The frame above the tab body is IDENTICAL to screens 10 and 11

Back link · kicker · title · `ACTIVE` pill · sub-line · `Duplicate · Edit ·
Retire` · tabs with `Audit` active · the four KPI tiles · the `NOT WORKED OUT YET`
bar.

Tab description line: `What the rate has been, and who changed it.`

## 2 · Panel `Audit` — a FOUR-column table

| # | header | alignment |
|---|---|---|
| 1 | `EFFECTIVE` | left |
| 2 | `RATE` | left |
| 3 | `WHY IT CHANGED` | left |
| 4 | `BY` | left |

Drawn rows:

| Effective | Rate | Why it changed | By |
|---|---|---|---|
| `06/01/2026` | `6.25%` | `State rate increase, HB-1441` | `Dana Whitfield` |
| `01/01/2024` | `6.00%` | `First recorded` | `—` |

⚠ **EVERY FIGURE AND NAME HERE IS AN ILLUSTRATION (B14 rule 37).** What is NOT an
illustration is the SHAPE: two rows newest-first, a reason on every row, and a
dash where nobody was recorded. ⚠ **`6.25%` AND `6.00%` ARE MONEY-ADJACENT — see
§8.**

## 3 · Accent callout below the table

| kicker | sentence |
|---|---|
| `DATED` | `A bill issued last month has to work out to the same figure forever. That is why a tax in force is corrected with a new version and never edited in place.` |

## 4 · Primary action

`Edit`, **from the header** — *"which writes the next row here."*

## 5 · States — the blueprint's own block, verbatim

| state | drawn behaviour |
|---|---|
| **One version** | *"`First recorded`, and a dash where nobody was stored. History is never filled in backwards."* |
| **A future version** | *"Listed above the one in force, marked Scheduled with its start date."* |

## 6 · Components named in the frame

`Panel` `VersionTable` `Callout dated`

---

## 7 · WHAT THE PRODUCT DOES — file and line evidence

**The drawn table is absent.** The history tab renders an `ArrivesWith` and the
dated banner:

```
07-frontend/src/features/rating/DefinitionDetailPage.tsx:712-722
  if (isHistoryTab(props.tab)) {
    return (
      <>
        <ArrivesWith title={heading} message={t("rating.definition.versions.arrivesWith")} />
        <DatedBanner t={t} />
      </>
    );
  }
```

| drawn | built? | evidence |
|---|---|---|
| tab named `Audit` (not `Versions`) | ✅ **changed since the drawing was read** | `DEFINITION_TABS.tax` ends in `"audit"`, `definitionDetail.tsx:103`; `isHistoryTab` knows both spellings while the CHARGE kind still says `versions` |
| tab description `What the rate has been, and who changed it.` | ❌ | nothing renders between the tab strip and the KPI strip |
| the four KPI tiles as drawn | ❌ | same gap as screen 10 §10.4 |
| `NOT WORKED OUT YET` bar | ❌ | same gap |
| panel `Audit` with a version table | ❌ **NOT BUILT** | `VersionTable` exists nowhere in `07-frontend/src` ⟨grepped⟩; the panel is an `ArrivesWith` whose message is `rating.definition.versions.arrivesWith` — *"This tab lists the object's own version history … no endpoint serves those versions yet."* |
| `DATED` callout, kicker + sentence | ⚠ **half built** | `DatedBanner`, `DefinitionDetailPage.tsx:771-784`, draws the `DATED` kicker correctly — but its body is `rating.definition.dated.body = "Bills always use the version in force on the usage date."`, **not** the drawn two-sentence *"A bill issued last month has to work out to the same figure forever…"* |
| primary action `Edit` from the header | ⚠ | the button is live, but on a tax **in force** it dead-ends — see §9 |

### What the server can and cannot answer today

The correction chain **is served on the tax row**:
`06-backend/apps/rating/selectors.py:2896-2898` (`corrects_tax_id` · `superseded_by_tax_id` · `correction_reason`) publishes `corrects_tax_id`,
`superseded_by_tax_id` and `correction_reason`, and `POST /taxes/{id}/corrections`
mints the next dated row (`06-backend/apps/rating/api.py:447`, route at `:784`).

**So three of the drawn table's four columns have a source per row** —
`effective_from` (EFFECTIVE), `rate_display` (RATE) and `correction_reason` (WHY IT
CHANGED). What is missing is (a) a read that returns the CHAIN rather than one row
at a time, and (b) the `BY` column, which is an `audit_log` actor and **must not be
fetched by filtering `audit_log`** — `definitionDetail.tsx`'s own §10 note and the
source-as-text guard in `DefinitionDetail.test.tsx` forbid exactly that: *"the
object's own version table, never a filtered `audit_log` query."*

---

## 8 · ❄️ FROZEN / MONEY — REPORTED, NOT TOUCHED

The drawn rate history is the audit surface for a **statutory rate that priced
issued bills**. Hard rule 4 (financial immutability) and `BR-RAT-104` govern how a
rate is corrected; `B4` governs the arithmetic. **Nothing in this file proposes a
figure, a rounding or a correction rule.** The two drawn percentages are
illustrations.

## 9 · ⚠ THE PRIMARY ACTION DOES NOT WRITE THE NEXT ROW

Page 37: *"`Edit`, from the header, which writes the next row here."*

At `2.234.19` it cannot, for a tax in force. The full chain is written out in the
`p030` file §11; in one line: `Edit` opens `TaxWizard`, which refuses everything
for an in-force tax and says *"that route has not been built"* — while
`POST /taxes/{id}/corrections` IS built and its typed client `correctTax`
(`07-frontend/src/api/endpoints.ts:4996-5004`) is **called by nothing**.
`TaxWizard.tsx`'s own `E6` exception (line 1829) says the correction form *"is the
tax detail's Versions tab"* — **this tab** — *"and is not built here"*. It is not
built there either.

**So the one screen the blueprint gives this action to is the screen that was
supposed to hold the form.** Recorded; filing left to the parent lane.

## 10 · THE BLUEPRINT AGAINST ITSELF — recorded, not resolved

1. **`EXISTS BEHIND` + `NO COMMITMENT`** over a section whose own WHAT CHANGED
   says *"The tab explained that no endpoint served it"* and then specifies a
   table for it. By the page-2 legend that is `NEW READ`, and `NO COMMITMENT`
   means nobody has undertaken to build it. Same shape as screen 11 §8.
2. The blueprint's `What was wrong` — *"Rate history rendered a sentence about its
   own absence, on the object whose own header calls rate history an audit
   artefact"* — is still an accurate description of the product at HEAD.

## 11 · FOR THE PRODUCT OWNER

* **Whether the correction chain should be READ as a list is not a UI question.**
  Three of four columns are already stored per row; the `BY` column needs a
  decision about where an actor comes from that is not `audit_log`. One sentence
  settles it.

## 12 · NOT VERIFIABLE WITHOUT THE APP RUNNING

* Nothing on this tab — the body is a stated absence plus one banner, and both
  read the same in a browser as in the source.

---

## 13 · ONE RECORD-ROT NOTE FOUND WHILE READING (no defect filed)

`07-frontend/src/features/rating/TaxWizard.test.tsx:766-768` still says
*"pressing Continue through all **four** steps and saving"*. The wizard has been
three steps since 2026-09-08. A `todo` string, so nothing fails.

---

## 14 · WHAT WAS BUILT — 2026-09-10, the CR-087 tax-screens maintenance lane

**The tab body is built**, on the same PO ruling of 2026-09-10 (*"build"*) that
covers `p034`. §11's question to the Product Owner — *"whether the correction
chain should be READ as a list"* and *"where an actor comes from that is not
`audit_log`"* — is answered by the same word, and the actor is a COLUMN.

| §7 finding | now |
|---|---|
| panel `Audit` with a version table | **BUILT** — `TaxAuditTab`, `taxDetailTabs.tsx`, on the kit's `PlainTable` |
| the four columns | **BUILT** — `EFFECTIVE` · `RATE` · `WHY IT CHANGED` · `BY` |
| the chain read | **BUILT** — `GET /taxes/{id}/versions`, `selectors.tax_correction_chain` |
| the `BY` column | **BUILT** — `taxes.corrected_by`, rating migration `0032` |
| state *One version* | **BUILT** — `First recorded` and a dash, both worded on the screen and neither stored |
| state *A future version* | **BUILT** — the row carries `Scheduled` beside its start date |
| tab named `Audit`, address unchanged | **unchanged** — PO 2026-09-10: *"Change the label, keep the address"* |
| the tab description line | **BUILT**, shortened to B14 rule 33's cap |
| the `DATED` callout's drawn body | **NOT BUILT** — `DatedBanner` keeps `rating.definition.dated.body`, which is the shared banner every definition kind draws. Re-wording it for the tax alone would give one sentence two forms; recorded rather than changed |
| primary action `Edit` *"writes the next row here"* | **TRUE NOW** — `p030` §16.1 |

### ⚠ WHY THE ACTOR IS A COLUMN AND NOT AN `audit_log` LOOKUP

`correct_tax` already writes two `audit_log` rows naming the acting user, so the
`BY` column looks stored. It is not stored *where it can be read*: §7 records
that `DefinitionDetailPage.tsx`'s own note and the source-as-text guard in
`DefinitionDetail.test.tsx` forbid a filtered audit query behind this tab — and
CLAUDE.md hard rule 4's 2026-09-02 narrowing gives the sharper reason,
**`audit_log` is PRUNED on a retention schedule**. A rate history whose authors
come from there loses them on the pruning run, silently, on the one screen whose
job is to say who changed a statutory rate.

`corrected_by` is NULL on every row written before the column existed and the
screen renders a dash for it. **History is never filled in backwards**, which is
the drawn behaviour, and a test asserts that ABSENCE so a later lane that
"helpfully" back-fills from `audit_log` goes red rather than shipping invented
authorship.

### DIVERGENCES, RECORDED

1. **NO PAGINATION FOOTER (B14 rule 16)** — same argument as `p034`; the read is
   bounded by the number of corrections filed against one statutory rate.
2. **Every drawn figure and name is an illustration** (B14 rule 37): `6.25%`,
   `6.00%`, `State rate increase, HB-1441` and `Dana Whitfield` are asserted
   nowhere. What IS asserted is the SHAPE — two rows newest-first, a reason on
   the corrected row, a dash on the row nobody corrected.
3. §13's record-rot note (`TaxWizard.test.tsx` still saying *four* steps) is
   **still open** — that file belongs to another lane's in-flight change.
