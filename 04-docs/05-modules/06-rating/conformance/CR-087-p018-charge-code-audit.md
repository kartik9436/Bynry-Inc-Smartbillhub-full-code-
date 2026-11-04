# 06 · Charge code → View · Audit — THE DRAWN SPEC

`CHG-01 (charge)` · route `/:tenant/plans-rates/charge-codes/:id?tab=audit` ·
**blueprint pages 18–20**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section
`01 CHARGE CODES`, screen `06`. The screen head and the frame start on **page
18**, the frame's table and the `DATED` callout are at the top of **page 19**, the
specification runs to the top of **page 20**. Read as RENDERED pages — the
four-column table and its two-line second row are drawn.

**State chips on the screen head:** `EXISTS BEHIND` · `NO COMMITMENT`
**Screen question, verbatim:** *"What has this charge cost, and who changed it?"*

**What this file is.** Only the **bordered grey frame on pages 18–19** is the
specification. The amber *"What was wrong"* block is the problem statement:
*"The tab rendered a sentence explaining that its own content did not exist yet,
under a name no other module uses."*

⚠ **THE `EXISTS BEHIND` CHIP IS FALSE FOR THIS SCREEN AT 2.234.19.** Page 2
defines it as *"the screen is drawn and the data behind it is served"*. **There is
no version table for a charge code anywhere in this product** — no model, no
migration, no endpoint. See the diff.

⚠ **B14 rule 37** — `06/01/2026`, `$45.0000`, `01/01/2025`, `$38.0000` and
`Dana Whitfield` are ILLUSTRATIONS. None is recorded as a requirement, and none
may be asserted in a test.

---

## 1 · Header — identical to screens 04 and 05, `Audit` tab active

| slot | drawn |
|---|---|
| back link | `← Charge codes` |
| kicker | `CHARGE CODE · CONN · ONE-TIME` |
| title (H1) | `Connection fee` |
| status | `ACTIVE` *(pill)* |
| sub-line | `GL account 4200-01 — Connection revenue · Applying it creates a billable item that references the version in force, so an issued bill never changes.` |
| actions | `Duplicate` · `Edit` · `Retire` *(danger)* |

## 2 · Tabs — THREE, `Audit` active

`Overview` | `Plans` | `Audit`

## 3 · The tab description line

`What it has cost, and who changed it.`

## 4 · Tiles and the `NOT WORKED OUT YET` band — unchanged

The same four tiles and the same two-row absence band are drawn above the tab
body. See `CR-087-p013-charge-code-overview.md` §5–§6.

## 5 · The panel — `Audit`

*(no sub-line drawn)*

## 6 · The table — FOUR columns, no action column

| # | header | cell, as drawn |
|---|---|---|
| 1 | `EFFECTIVE` | `06/01/2026` |
| 2 | `AMOUNT` | `$45.0000` |
| 3 | `WHY IT CHANGED` | `Annual review — cost recovery` |
| 4 | `BY` | `Dana Whitfield` |

**The two drawn rows, in order:**

| EFFECTIVE | AMOUNT | WHY IT CHANGED | BY |
|---|---|---|---|
| `06/01/2026` | `$45.0000` | `Annual review — cost recovery` | `Dana Whitfield` |
| `01/01/2025` | `$38.0000` | `—` *(and, under it, small: `Nothing was written against this version.`)* | `—` |

**Newest first.** The dash-plus-sentence cell in row 2 is drawn as ONE cell with
two lines, not as two rows.

## 7 · The accent callout under the table

| kicker | `DATED` |
|---|---|
| body | `Bills always use the version in force on the usage date. Changing a price never re-prices a bill already issued.` |

## 8 · States — the blueprint's own STATES block, verbatim

| state | drawn behaviour |
|---|---|
| **One version** | *"The row reads *First recorded* and the By column is a dash where nothing was stored — history is never invented backwards."* |
| **The person has left** | *"*No longer has an account*, rather than a blank or a stale name."* |

## 9 · Components named in the frame

`Panel` `VersionTable` `Callout dated`

## 10 · FOR · HOW YOU GET HERE (pages 19–20)

* **FOR** — *"Anyone answering *why was I charged $38 and my neighbour $45*."*
* **HOW YOU GET HERE** — *"The **Audit** tab."*
* **PRIMARY ACTION** — *"**Edit**, from the header, which creates the next row
  here."*
* **WHAT CHANGED · THE NAME** — *"It was *Versions*. Eight detail screens in this
  product call this tab **Audit**; Plans & Rates was the only module using its own
  word. Same correction as the rate schedule — **say if you would rather it stayed
  Versions here** and it is one string."*
* **WHAT CHANGED · THE CONTENT** — *"The tab rendered a sentence explaining that
  no endpoint served it. It shows what the code has cost and from when, and the
  *why* column is filled by the reason box added to the save screen — the two
  changes only work together."*
* **THE REASON IS OPTIONAL, SO A DASH IS A REAL ANSWER** — *"A version can
  legitimately carry none. The cell says *nothing was written against this
  version* rather than looking broken."*

## 11 · Absences — drawn as absent, do not fill them

* **No `Version` number column**, no `V1`/`V2`.
* **No `Status` column** — no Draft / Active / Superseded.
* **No `Superseded` column, no `Filed as` column.**
* **No row actions**, nothing to click.
* **No toolbar and no pagination footer are DRAWN.**

---

## THE DIFF — the drawn frame against the code at 2.234.19

The tab body is `DefinitionTabBody` in
`07-frontend/src/features/rating/DefinitionDetailPage.tsx`, **lines 681–766**.

### 1 · THE DRAWN ADDRESS DOES NOT OPEN THIS TAB — IT OPENS THE OVERVIEW

The frame's route is `…/charge-codes/:id?tab=audit`. The charge kind's tab list
is (`definitionDetail.tsx:67`):

```
charge: ["overview", "amounts", "applicability", "plans", "versions"],
```

`"audit"` is **not in it**, and `definitionTabFrom`
(`DefinitionDetailPage.tsx:131–134`) falls back silently to the kind's first tab:

```
export function definitionTabFrom(kind: DefinitionKind, raw: string | null): string {
  const tabs = DEFINITION_TABS[kind];
  return tabs.includes(raw ?? "") ? (raw as string) : tabs[0];
}
```

**So a link to the drawn address lands on Overview with no error.** The charge's
tab id is still `versions` (`definitionDetail.tsx:131`); the discount moved to
`audit` on 2026-09-08 (`:85`, CR-087 C2) and the tax followed (`:104`), and the
file names the charge as the one left at `:97–99`.

### 2 · BUT THE TAB ALREADY *READS* `Audit`, SO HALF OF "WHAT CHANGED · THE NAME"
IS ALREADY DONE

`rating.definition.tab.versions` = **`Audit`** in `en.json`, and
`rating.definition.panel.versions` = **`Audit`**. The label a clerk sees is
already the word every other module uses; only the ID (and therefore the
deep-link address) still says `versions`. **The blueprint's *"under a name no
other module uses"* is stale as a statement about the rendered word and true as a
statement about the address.** Verified by reading both keys and
`DefinitionDetailPage.tsx:450–453`, which builds every tab label as
`t(\`rating.definition.tab.${id}\`)`.

### 3 · THE TABLE DOES NOT EXIST, AND NEITHER DOES THE DATA

`DefinitionDetailPage.tsx:713–722`:

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

`rating.definition.versions.arrivesWith` = *"This tab lists the object's own
version history — what the price was, from when, and the reason someone wrote for
the change. It is not the audit log, and no endpoint serves those versions yet."*

⚠ **AND IT IS NOT A MISSING READ OVER EXISTING ROWS — THERE ARE NO ROWS.**
`06-backend/apps/rating/models.py` declares `TariffVersion` (`:225`) and
`PlanVersion` (`:1586`) and **no charge version model at all**; `Charge`
(`:769`) carries no `effective_from`, and the migration folder holds nothing for
one. `06-backend/apps/rating/api.py:774–776` has no
`charges/{id}/versions` beside the `rate-schedules/{id}/versions` (`:771`) and
`discounts/{id}/versions` (`:791`) that do exist. `presentCharge` says so itself
at `definitionDetail.tsx:466–469`: *"The version is the fourth part on the drawing
and is DELIBERATELY ABSENT here: charge codes carry no version table (§10 ·
DEF-357), and printing `V1` would assert a history the product does not keep."*

**So screen 06 is a model + migration + write path + endpoint + screen, not a
screen.** It is also the second half of screen 03's reason box: the frame itself
says *"the two changes only work together"*.

### 4 · THE `DATED` CALLOUT IS BUILT AND ITS SENTENCE IS HALF THE DRAWN ONE

`DatedBanner` at `DefinitionDetailPage.tsx:771–783` renders
`rating.definition.dated.label` = `Dated` and
`rating.definition.dated.body` = **"Bills always use the version in force on the
usage date."**

The drawn body has a second sentence: *"Changing a price never re-prices a bill
already issued."* It is absent here — and it IS present in the charge's own
policy sub-line (`rating.definition.charge.policy`, `definitionDetail.tsx:477`)
and in the wizard's drawn `WHAT SAVING DOES` box. One sentence, three places; B14
rule 32's one-sentence budget says which one keeps it.

The banner's markup matches the drawn callout — `border-l-2 border-l-accent`, a
`Kicker` label, a `Note` body, `role="note"`
(`DefinitionDetailPage.tsx:772–782`).

### 5 · THE VOCABULARY ALREADY EXISTS ONE SCREEN OVER, AND THE WORDS DIFFER

The rate schedule's version table is built and its catalogue is the closest
existing match:

| drawn | nearest built key | reads |
|---|---|---|
| `EFFECTIVE` | `rating.rateDetail.versions.col.effective` | `Effective` ✓ |
| `AMOUNT` | — | no equivalent (a schedule version has no single amount) |
| `WHY IT CHANGED` | `rating.rateDetail.versions.col.change` | **`Change`** ✗ |
| `BY` | `rating.rateDetail.versions.col.by` | `By` ✓ |
| *"Nothing was written against this version."* | `rating.rateDetail.versions.changeUnavailable` | **"The note describing a change is written when a version is filed. Nothing records it yet."** ✗ |
| *"No longer has an account"* | `rating.rateDetail.versions.byUnknownUser` | **"The person who filed this version no longer has an account."** ✗ |
| *"First recorded"* | — | no key |

Three of the drawn strings are re-wordings of sentences that already exist. B14
rule 36 asks for one word per thing across the product — if the charge's column
becomes `Why it changed`, the rate schedule's `Change` is the other half of that
decision, and a PO sentence settles both at once.

### 6 · WHAT IS ALREADY RIGHT

* The tabs, tiles and header above the tab body are page-level exactly as drawn.
* `isHistoryTab` (`definitionDetail.tsx:141–143`) is the single predicate that
  knows both spellings, so moving the charge to `audit` is one array entry plus
  its test — and the file says `VERSIONS_TAB` is deleted when it moves.
* The `DATED` banner already renders on this tab and only on this tab.

---

## DIVERGENCES — B14 rule 38 and B14 rule 16

1. **NO PAGINATION FOOTER IS DRAWN AND B14 RULE 16 REQUIRES ONE** on every list
   table. A charge code repriced monthly for ten years is 120 rows. The UI rules
   win; the frame's absence is not a licence to build an unpaginated list, and
   `NFR-3` (universal server pagination) is a `CLAUDE.md` hard requirement rather
   than a preference.
2. **`VersionTable` IS NOT A KIT COMPONENT.** `components/DataTable.tsx` is the
   shared table; a second one is B14 rule 36's own finding. Recorded as a naming
   divergence only.

---

## THE BLUEPRINT AGAINST ITSELF — recorded, not resolved

1. **THE `EXISTS BEHIND` CHIP CONTRADICTS THE FRAME'S OWN WHAT-CHANGED TEXT** —
   the chip says the data is served, the paragraph beside it says *"no endpoint
   served it"*. And the code goes further than the paragraph: there is no model
   either.
2. **`NO COMMITMENT` ON A SCREEN THAT NEEDS A MIGRATION.** Page 2: *"If a thing
   is not in a commitment card, nobody has undertaken to build it"* and *"A screen
   no specification covers carries `NO COMMITMENT` — and that absence is the
   finding, not an oversight."* Screens 03, 05 and 06 all carry `NO COMMITMENT`
   and all three need server work; only screen 04 has a card (`PRB-04`), and
   `PRB-04` covers only the two absent tiles. **The finding is recorded exactly as
   page 2 asks.**
3. **THE REASON COLUMN IS FILLED BY A BOX THAT HAS NOWHERE TO WRITE.** Screen 03
   makes `WHY THIS CHANGED` required; this screen's `WHY IT CHANGED` column is
   where it lands. With no version row to attach it to, the document specifies a
   required input with no store. The two frames are consistent with each other
   and jointly inconsistent with the schema.

---

## FOR THE PRODUCT OWNER

1. **THE BLUEPRINT ASKS A DIRECT QUESTION AND IT IS STILL OPEN.** Page 19,
   verbatim: *"say if you would rather it stayed Versions here"*. The rendered
   label is ALREADY `Audit` in all eleven catalogues; what is still `versions` is
   the tab id in the URL. One sentence: *the tab already reads "Audit" like every
   other screen — do you want the web address to say audit too, or leave it?*
2. **`WHY IT CHANGED` vs `Change`.** The rate schedule's identical column is
   headed `Change` today. One word, two screens; B14 rule 36 wants one.

---

## WHAT COULD NOT BE VERIFIED WITHOUT THE APP RUNNING

* Nothing on this tab can be exercised at all — it renders one sentence and a
  banner. The two drawn states (`One version`, `The person has left`) have no
  code path to reach.
* Whether `?tab=audit` visibly falls back to Overview or flashes — the fallback
  is in the source (`DefinitionDetailPage.tsx:131–134`, `:269`) and was read, not
  clicked. No stack was booted; hard-won law 6.

## THE ELEVEN CATALOGUES

`rating.definition.tab.versions`, `rating.definition.panel.versions`,
`rating.definition.versions.arrivesWith`, `rating.definition.dated.label` and
`rating.definition.dated.body` are present in all eleven locales.
`versions.arrivesWith`, `dated.label` and `dated.body` are among the 50
`rating.definition.*` keys that are **English verbatim** in `es-MX`, `hi`,
`id-ID`, `ja-JP` and `ko-KR` — B14 rule 35. Every string the drawn table needs
(`EFFECTIVE`, `AMOUNT`, `WHY IT CHANGED`, `BY`, *"Nothing was written against this
version."*, *"First recorded"*, *"No longer has an account"*) exists in no locale.

---

## ⚠ AMENDED 2026-09-10 — HALF BUILT, HALF SIZED, AND NOT STUBBED

**PO ruling 2026-09-10: *"build"*** for the four empty tab bodies, and
**separately** *"Change the label, keep the address"* for this tab's name.
`DEF-RAT-4832`.

### WHAT IS DONE

**§1 is FIXED — `?tab=audit` opens this tab.** It used to fall back to the
Overview, silently: `definitionTabFrom` could not tell a mistyped tab from a
synonym, so a link to a screen that exists opened a different screen with no
error and no log. A history spelling the kind does not use now resolves to the
one it does, **in both directions** — a `?tab=versions` link to a DISCOUNT,
written before that kind was renamed on 2026-09-08, landed on its Overview for
the identical reason.

**§2's other half is deliberately NOT done: the address stays `versions`.** The
PO's ruling is explicit, and links already sent to people keep working. Only what
is ACCEPTED widened; `selectTab` still writes the kind's own id back.

### WHAT IS NOT DONE, AND WHY A STUB WOULD BE WORSE THAN THE SENTENCE

**§3 stands unchanged: there are no rows, so there is no read to write.** This is
a model, a migration and a write path before it is a screen — and it is the same
piece of work as screen 03's `WHY THIS CHANGED` box, which the blueprint itself
says *"only work together"*.

**The order, sized:**

1. a `ChargeVersion` model + migration — `charge`, `effective_from`, the priced
   state, `change_reason`, and the actor as `{id, name}` **on the row**
   (`DEF-367`), so the `BY` column survives the `audit_log` retention prune;
2. a write path: `update_charge` files a version rather than only mutating the
   row — which is where step 3's reason box lands;
3. `GET /charges/{id}/versions`, paged (`NFR-3`: a code repriced monthly for ten
   years is 120 rows, and the frame draws no footer — rule 16 wins there as it
   does on the Plans tab);
4. the screen, which is then the smallest part of it.

⚠ **AND ONE QUESTION THE PO SHOULD SEE BEFORE ANY OF IT IS BUILT, BECAUSE THE
DRAWING CANNOT ANSWER IT.** The drawn table puts a single `AMOUNT` column against
each version. A charge code that prices **per size and per class** has no single
amount — that is exactly what `CR-087` A1 shipped on 2026-09-08 — so a one-figure
history column is honest for a scalar code and wrong for every sized one. One
sentence: *when a charge code prices eight different amounts, what should the
history column show?*

### §5's VOCABULARY QUESTION IS STILL OPEN

`WHY IT CHANGED` here versus `Change` on the rate schedule, and the two absence
sentences that are re-wordings of existing ones. **Nothing was minted**, because
minting one half of a two-screen word is how a product acquires two spellings —
B14 rule 36's own finding. It goes with the work above.
