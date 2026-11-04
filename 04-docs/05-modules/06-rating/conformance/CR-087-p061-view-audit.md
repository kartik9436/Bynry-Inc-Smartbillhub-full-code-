# 20 · Rate schedule → View · Audit — THE DRAWN SPEC

`S11 · RAT-02` · route `/:tenant/plans-rates/rates/:id?tab=audit` · **blueprint pages 61–63**

**Source:** `05-prototype/SMARTBillHub Plans & Rates Blueprint.pdf`, section opening
on page 61, **frame drawn across pages 61–62**, specified on 62–63. Read as
RENDERED pages — the six-column table with a date RANGE in one cell, the two
stacked lines in the `WHAT CHANGED` and `BY` cells of the superseded row, and the
closing `DATED` callout are only legible as a picture; text extraction prints the
header row twice and the `STATES` legend in the middle of the table.

**State chip:** `EXISTS BEHIND`
**Commitment:** `NO COMMITMENT`.

**Masthead warning, applied.** As-built at **2.232.0**; re-checked at **2.234.19**,
and **one of this section's as-built claims is stale** — see D3.

---

## 1 · Header, actions, tabs, tiles — identical to screens 18 and 19

`← Rate schedules` · eyebrow `RATE SCHEDULE · WATER · RESIDENTIAL · TIERED · V3` ·
title · `ACTIVE` pill · the three-part sub-line · `Duplicate` `Edit` `Retire` ·
tabs `Overview | Plans | Audit` with **`Audit` active** · the four tiles and the
`NOT WORKED OUT YET · Revenue` band.

**Tab explainer, one sentence:**
`Every version this schedule has had, and who changed it.`

## 2 · The panel — `Audit`

**Heading:** `Audit` · no hint line.

## 3 · The table — SIX columns, in this order

| # | header | content |
|---|---|---|
| 1 | `VERSION` | `2027-A` · `v3` · `v2` |
| 2 | `EFFECTIVE` | a **RANGE** — `01/01/2027 →` · `06/01/2026 – 12/31/2026` · `01/01/2026 – 05/31/2026` |
| 3 | `FILED AS` | `PUC 2026-4417` · `PUC 2026-1180` · `—` |
| 4 | `WHAT CHANGED` | `Annual inflation adjustment, +4.0%` · `Rebalance after the summer review` · `—` over `Nothing was written against this version.` |
| 5 | `BY` | `Dana Whitfield` · `Dana Whitfield` · `—` over `No longer has an account` |
| 6 | `STATUS` | pills — `SCHEDULED` · `ACTIVE` · `SUPERSEDED` |

⚠ **SEVEN COLUMNS BECAME SIX.** Page 62: *"`Superseded` was its own column showing
the next version's start. It is folded into `Effective` as a range, which is how a
person reads a date span."*

⚠ **AN OPEN-ENDED RANGE IS A DATE AND AN ARROW** — `01/01/2027 →`, not
`01/01/2027 – —`.

⚠ **A DASH IN `WHAT CHANGED` IS A REAL ANSWER AND SAYS SO.** Page 62: *"On your
instruction the change note is not required, so a version can legitimately carry
none. The cell says `nothing was written against this version` rather than looking
broken."*

⚠ **B14 rule 37 — the dates, the dockets, `Dana Whitfield` and `+4.0%` are
ILLUSTRATIONS.** The shape is: a filed label, a range, a docket, an authored
sentence, a person, a state.

## 4 · Closing callout, accent

| legend | sentence |
|---|---|
| `DATED` | `Bills always price usage with the version in force on the read date — a January bill for December usage uses v3 even after 2027-A starts.` |

## 5 · States — verbatim

| state | drawn behaviour |
|---|---|
| **No version activated** | *"`No version has been activated yet.`"* |
| **A future version** | *"Listed above the one in force, marked Scheduled with its start date."* |
| **The person has left** | *"`No longer has an account`, rather than a blank or a stale name."* |

## 6 · Components named in the frame

`Panel` `VersionTable` `StatusPill` `Callout dated`

## 7 · FOR · HOW YOU GET HERE · PRIMARY ACTION

* **FOR** — *"An auditor, a regulator's question, or a clerk defending an old bill."*
* **HOW YOU GET HERE** — *"The `Audit` tab."*
* **PRIMARY ACTION** — *"`Edit`, from the header, which creates the next row here."*

---

# THE DIFF — drawing against the code at 2.234.19

Code: `RateScheduleDetail.tsx` — `VersionsTab` at line **1445**.

## D1 · THE TAB, THE PANEL AND THE ROUTE ALL SAY `Versions & filings`

| surface | drawn | built |
|---|---|---|
| tab label | `Audit` | `rating.rateDetail.tab.versions` = `Versions & filings` |
| panel heading | `Audit` | `rating.rateDetail.panel.versions` = `Versions & filings` |
| URL | `?tab=audit` | `?tab=versions` (`RATE_DETAIL_TABS`, `RateScheduleDetail.tsx:185`) |
| explainer | `Every version this schedule has had, and who changed it.` | `rating.rateDetail.explainer.versions` = *"Every version this schedule has had, and what was filed for it."* |

Page 62: *"It was called `Versions & filings`. **Eight detail screens in this
product call this tab `Audit`** — assets, bills, customer accounts, premises,
units, cycles, routes, work orders. Plans & Rates was the only module using its own
word. It is Audit."*

⚠ **THE URL CHANGE IS THE EXPENSIVE HALF, NOT THE LABEL.** `?tab=versions` is a
shareable address (`routing/screenIds.ts:694-699`) and the file's own note explains
why it is a search param — *"a link to `the versions of this schedule` is
shareable"*. Renaming it breaks any link already sent. **Recorded, with the
mitigation that `rateDetailTabFromParam` (`:193-196`) already falls back rather
than erroring, so an old link would silently land on Overview.**

## D2 · SEVEN COLUMNS, NOT SIX — `Superseded` is still its own

`RateScheduleDetail.tsx:1459-1483` declares seven `<th>`s:

`Version` · `Effective` · **`Superseded`** · `Filed as` · `Change` · `By` · `Status`

`rating.rateDetail.versions.col.superseded` = `Superseded`, and the cell at
`:1505-1515` renders `effective_to` alone. The drawing folds the two dates into
one `EFFECTIVE` cell as a range, and drops the seventh header.

Header wording also differs: column 5 is `Change` (`versions.col.change`) where
the drawing says `WHAT CHANGED` — the same words as the step-4 field that writes
it, which is the RULES clause *"One fact has one wording everywhere."*

## D3 · ⚠ THE `WHAT CHANGED` AND `BY` COLUMNS ARE **NOT** EMPTY — the blueprint's complaint is stale

Page 61 opens: *"two of its six columns showed an em-dash on every row"*, and page
62 says they are *"filled, because the reason box on the change screen writes to
the version."*

**Both were already filled at 2.232.0 and are filled now.**
`RateScheduleDetail.tsx:1527-1531` renders `line.version.change_reason` with a
stated absence behind it, and `SubmitterCell` (`:1433-1445`) renders
`submitted_by.name` with **two distinguishable absences**:

```tsx
  if (submitter === null) return <Absent reason={t("…versions.byUnavailable")} />;
  if (submitter.name === null) return <Absent reason={t("…versions.byUnknownUser")} />;
  return <span>{submitter.name}</span>;
```

`rating.rateDetail.versions.byUnknownUser` = *"The person who filed this version no
longer has an account."* — which is the drawn `The person has left` state, already
built. The file's lifecycle block dates the closures: `DEF-280` and `DEF-367`,
Wave E, 2026-08-21.

**What IS different is the WORDING of the empty `WHAT CHANGED` cell:**

| drawn | built |
|---|---|
| `Nothing was written against this version.` | `rating.rateDetail.versions.changeUnavailable` = *"The note describing a change is written when a version is filed. Nothing records it yet."* |

⚠ **THE BUILT SENTENCE IS NOW FALSE.** *"Nothing records it yet"* was true before
`DEF-280`; `tariff_versions.change_reason` records it today. It is a hard-won law 1
survivor — a sentence that described the code when it was written and describes
nothing now — and the drawn replacement is exactly right. **This one is worth
fixing on its own merits, independent of the rest of the tab.**

## D4 · A DASH IN `BY` HAS TWO MEANINGS AND THE DRAWING SHOWS ONE

The drawn superseded row shows `—` over `No longer has an account`. The code
distinguishes **two** absences (D3) and its own comment says why (`:1423-1432`):
*"one says **we recorded a person and cannot name them now**, the other says
**nobody was recorded** — and a screen that collapsed them would be telling a
regulator the same thing about two different situations."*

**The drawing draws one of the two and does not contradict the other.** Recorded so
a lane building the frame literally does not collapse them.

## D5 · `STATUS` IS A PILL AND IT IS BUILT

`RateScheduleDetail.tsx:1542-1546` renders `RatingStatusPill` with
`stem="rating.rateDetail.versions.status"`, whose four values are `Active`,
`Draft`, `Scheduled`, `Superseded` — the drawn three plus the draft case. **Matches
the drawing.** (Contrast the Plans tab, where the same pill is a plain word — see
`CR-087-p058-view-plans.md` D7.)

## D6 · THE `DATED` CALLOUT IS BUILT, AND ITS EXAMPLE VERSION DIFFERS

`RateScheduleDetail.tsx:1570-1578` renders the accent-ruled band with legend
`rating.rateDetail.versions.datedLabel` = `Dated` and body
`rating.rateDetail.versions.datedBanner` = *"Bills always price usage with the
version in force on the read date — a January bill for December usage uses v3 even
after **v4** activates."*

The drawing says *"…even after **2027-A** starts."* — a filed label rather than a
derived ordinal, which is the point `VersionLabelCell` (`:1403-1425`) makes about
never presenting a position as an identifier. **B14 rule 37 makes both
illustrations**, so this is a wording preference, not a contradiction. Recorded.

The code's own comment calls this sentence *"the strongest statement of the
propagation rule in the whole product and should be treated as the canonical
sentence for it"* — so if it changes, it changes everywhere it is quoted.

## D7 · ONE EXTRA NOTE THE DRAWING DOES NOT HAVE

`RateScheduleDetail.tsx:1565` renders
`rating.rateDetail.versions.draftOnLiveSchedule` = *"A rate change in preparation
is a version with a future effective date. It is listed above the one in force."*

That is the drawn `A future version` STATE stated as standing copy on every render.
Under B14 rule 32 (one sentence per section; a stated absence is a closed
`<details>`) it is a candidate for folding, and the drawing does not draw it.
**Recorded, not called a defect** — it carries `OQ-311`'s real limitation (a clerk
cannot START a rate case on a live schedule) which is worth keeping somewhere.

## D8 · THE TABLE IS A RAW `<table>`

Same as the Plans tab: `RateScheduleDetail.tsx:1457-1553` writes its own
`<thead>`/`<tbody>`. `VersionTable` is the frame's component name; the kit has
`PlainTable` and `DataTable`. See `CR-087-p058-view-plans.md` D6 — one decision
covers both tabs.

## D9 · WHAT IS BUILT AND RIGHT

* **`rating.rateDetail.versions.empty`** = `No version has been activated yet.` —
  the drawn `No version activated` state, **verbatim**.
* **`VersionLabelCell`** (`:1400-1418`) prints the FILED label and falls back to a
  derived ordinal **with a note saying it was counted, not filed**
  (`rating.rateDetail.versions.ordinalDerived`). The drawing shows `2027-A` beside
  `v3` and `v2` — a filed label and two derived ones — and this cell is what makes
  that distinction honest. Nothing in the drawing asks for it and it must not be
  lost.
* **A future version listed above the one in force** — the ordering the drawing
  shows, and `DEF-368`'s fix.
* **`Edit` in the header creating the next row here** — matches `PRIMARY ACTION`.

## D10 · ⚠ FIVE CATALOGUES RENDER THIS TAB IN ENGLISH

The 88-of-97 English-identical block (see `CR-087-p055-view-overview.md` D9) covers
every column header, every status word, both absence sentences and the `DATED`
banner in `es-MX`, `hi`, `id-ID`, `ja-JP` and `ko-KR`.

---

## ABSENCES — drawn as absent, do not fill them

* **No row actions.** No view, no diff, no roll-back, no print. The log is
  append-only and the code refuses even a disabled control on that ground
  (`RateChangesTab.tsx:19-24`, the same rule).
* **No toolbar, no filters, no pagination footer.**
* **No link to the bulk rate-change history** (`RateChangesTab`, the S9 History
  view). The drawing does not draw one.
* **No `Superseded` column** (D2).

---

## CONTRADICTIONS AND THINGS FOR THE PRODUCT OWNER

1. **`?tab=versions` → `?tab=audit` BREAKS SHARED LINKS (D1).** The label change is
   free; the URL change is not. **Both, one, or neither — one sentence to the PO.**

2. **`changeUnavailable` IS A FALSE SENTENCE ON A REGULATOR-FACING SCREEN (D3).**
   It tells an auditor that nothing records the change note, and something does.
   Independent of the redesign.

3. **THE OPTIONAL CHANGE NOTE COLLIDES WITH `BR-RAT-037` (carried from
   `CR-087-p048-create-step4-effective-approval.md`).** This tab's spec depends on
   the note being optional — *"a version can legitimately carry none"* — and the
   server refuses a new version without a reason. **The same PO question, and this
   is the screen that shows what the answer looks like.**

---

## ⚑ BUILT 2026-09-10 — `CR-087` RATE-SCHEDULE MAINTENANCE LANE

**D1 · THE TAB IS LABELLED `Audit` AND ITS ADDRESS DOES NOT MOVE.** PO ruling
2026-09-10, verbatim: *"Change the label, keep the address"*. The tab label, the
panel heading and the explainer are the drawn ones in all eleven catalogues;
`?tab=versions` is unchanged, so every link already sent still opens the right
tab. **The drawn `?tab=audit` is a divergence and is recorded as one.**

**D3 · THE FALSE SENTENCE IS GONE — worth doing on its own merits, and it was.**
`changeUnavailable` told an auditor *"The note describing a change is written when
a version is filed. Nothing records it yet"* over a column that has recorded it
since `DEF-280` closed on 21 August. It reads **"Nothing was written against this
version."** — the drawn sentence, in all eleven catalogues.

**D2 · SEVEN COLUMNS BECOME SIX.** `Superseded` is folded into `Effective` as a
RANGE, and an open-ended span is a date and an ARROW — `01/01/2027 →` — never a
date and an em-dash, because `01/01/2027 – —` reads as a MISSING value where the
end date is deliberately absent. The arrow carries an accessible name.
`versions.col.change` → `What changed`, the same words as the field that writes it.

**D8 · `PlainTable`** — one decision with the Plans tab, recorded there.

**D4 · DELIBERATELY UNTOUCHED.** The code distinguishes TWO absences in the `BY`
cell and the drawing shows one; collapsing them would tell a regulator the same
thing about two different situations. The test suite pins both.
**D6, D7 · UNCHANGED.** The `DATED` banner keeps its wording and now composes the
kit's `AccentBand` rather than a hand-rolled `<div>`; the `draftOnLiveSchedule`
note stays, carrying `OQ-311`'s real limitation.
**D10 · FILED, NOT SWEPT** — see `p055` D9.
