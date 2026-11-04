# CR-143-BRC07 — Size as a column on the asset registry, and in the column chooser

**Raised:** 2026-09-27, by the Product Owner, from the running product
(`smartbillhub.bynry.com/ottumwa-water-works/assets`, `v2.380.3`).
**Branch:** `BRC07`, `claude/kind-goldberg-k0acqg`. Number from `allocate.py cr`, checked free
against the remote with `allocate.py cr --verify 143` at allocation and again at push.
**Version:** `2.383.5`.
**Classification:** **CHANGE**, **screen-shaped.** The product does what was agreed: the Assets
blueprint draws ten columns on the Meters tab (Figure 1, p7) and its own remedy drawing stamps
them **`Ten columns, same order — UNCHANGED`** (Figure 52, p142). A size column is a new
requirement, not our miss, so this is a change and not a defect (`13-change-process.md` §1).
It is not ambiguous: the remedy drawing was the moment to add one and deliberately did not.
**Screen owner:** lane AST-SIZE, for the length of this change.
**Drawing file:** `05-prototype/01 Assets Menu Blueprint.pdf` — p7 (screen 01 Meters, as built)
and p142 (Figure 52, the R6 remedy), both rendered as IMAGES at scale 3 and read with eyes
(B14 rules 41/42).

---

## 0 · What arrived, in the requester's words

> *"on asset screen can you add size - column - since it si required for billing it is importan
> we show in list vview also - add it in column seelctor also"*

**The case behind it, in plain English.** A fire line is priced by its size: one 6" line is
`$60.00` a month and one 2" line is `$12.00`, and the count multiplies the price. Water works the
same way — the base charge is resolved *service → account type → size class*. So a clerk checking
a bill run against the asset list was being asked to audit an arithmetic whose **first input the
list did not show**. They had to open each asset one at a time.

---

## 1 · What is being reversed

**One drawn statement.** The Assets blueprint's Figure 52 carry-over table:
*"Ten columns, same order — UNCHANGED."* There are eleven on Meters now, and ten on Behind the
meter.

**Nothing signed moves.** No ❄️ FROZEN B4/B5 figure. No business rule changes: `BR-AST-500`
already says an asset carries a size class and already says a retired size must survive on the
record that priced with it. No money path, no migration, no schema change — **the column has been
on `assets` since `BR-AST-500` and the list read has been serving it since then.** What was
missing was a value a screen was *allowed to print*.

---

## 2 · Impact across the surfaces

| surface | impact |
|---|---|
| screens | **S49 Assets registry.** Meters gains one column between `SERVICE` and `MULT.`; Behind the meter gains one between `METER` and `EXPORT CAPACITY`. Both appear in the `▦` chooser, which is driven by the same `config.columns` array, so no second mechanism. **Sub-meters gains nothing** — `offersConnectionSize` refuses a size on a sub-meter, so the column could only ever be empty. |
| routes | none. |
| copy | **no new key.** `assets.col.sizeClass` = *Connection size* already exists in all eleven catalogues and is already the label on the edit form, the add wizard and the detail Fact. One pair of words for one fact. |
| API | the list read gains **one key**, `size_class_name`, beside the `size_class` it already served. Additive; nothing is removed or renamed. |
| schema / migrations / data | **none.** |
| money | none directly — this is a READ. It is a billing *input* becoming visible, which is the point. |
| `NFR-3` / `NFR-5` | honoured. One lookup for the whole page, and only when a row on that page carries a size; a page whose every size is null asks tenancy nothing. No cap added anywhere. |
| open questions | none opened, none closed. `OQ-1360` (the going-live customer's own fire list) and `OQ-1380` (may one size belong to two services) are untouched. |
| demo fixture | none. |

---

## 3 · What was already built and is now wrong

**Nothing.** This is additive. The one thing worth naming is not wrong but is a consequence:

**A clerk with a saved column preference will not see the new column until they ask for it.**
`columnsFromPreference` keeps only the keys a stored preference names, so `table.S49.columns`
saved before today does not contain `size_class`. A clerk who has never touched the `▦` chooser
gets the column immediately; one who has customised their columns finds it in the chooser,
unticked. That is the shared kit's existing behaviour on all 54 lists and changing it is exactly
the risk the PO ruled out of an Assets pass on 2026-09-12 (*"It's the right fix and it touches 54
lists at once"*). Recorded, not fixed.

**No lane is building on this screen right now.**

---

## 4 · The judgment calls, and why each went the way it did

**1 · The NAME, never the code.** `Asset.size_class` is TEXT holding a
`service_size_classes.code` — `W-58`, `FL-2`. B14 rule 32 keeps an internal code out of
clerk-facing copy, and the name is the only one of the two that carries a **unit**
(`Water 5/8"`), which CLAUDE.md hard rule 3 asks of any dimension on screen. The customer portal
settled the identical question one module along on 2026-09-11 (`DEF-CWP-4848` — *"the size class
as a person reads it, not the code"*); this is the staff-side half of the same answer and the
reasoning is reused rather than re-argued.

**2 · The names come from the TENANT's own list, not from the ratified constant.** A utility may
add its own size and may retire one. `service_size_class_names()` reads the tenant's rows,
**including inactive ones**, because `BR-AST-500` is explicit that a retired size must not vanish
from a record that already priced with it — filtering to active would blank the column on exactly
the rows a clerk is most likely to be auditing.

**3 · A code the list cannot name draws the dash, not the code.** Falling back to the code would
be the breach the whole path exists to avoid.

**4 · The cell's empty state is the registry's em dash, not the detail screen's sentence.** The
detail Fact says *Not recorded — a rate ladder that prices by size cannot price this meter*, which
is right on a detail screen and is **12 words in every row of a 50-row page** in a list. B14 rule
33 caps a fact at six and rule 32 gives a screen a description budget. So the list draws the same
dash `INSTALLED` draws.

**5 · The position.** Between `SERVICE` and `MULT.` on Meters, because service and size are the
two facts that pick the base charge (`BR-RAT-108`, R3) and belong together; `MULT.` multiplies a
metered quantity and stays beside the reading columns. The drawing does not speak to position, so
this is a judgment and it is written down rather than left to be inferred.

---

## 5 · Size, in plain English

One new read helper in tenancy, one seam wrapper in assets, one line in the page-row shaper, one
typed key, two column declarations and one cell renderer. **No migration, no new catalogue key,
no new component.** One new test file of seven cases.

---

## 6 · Rollback

Revert the commit. The column disappears; `size_class_name` stops being served; nothing else
moves, because nothing else reads it and no data was written.

---

## 7 · Version

`2.383.5` — a fix-level bump from `allocate.py version --bump fix`.

---

## 8 · One thing found and NOT fixed

`AssetDetailPage.tsx`'s Connection size Fact prints **`asset.size_class` — the bare code** to a
clerk, which is the same B14 rule 32 question this change answers for the list and which the
portal already answered for the customer. It is filed as `DEF-AST-7100` and left alone: it is a
different screen, and fixing it in a commit about the registry is what §14 of the UI skill calls
the silent fix.
