# Assets registry — SIZE is an ELEVENTH column, and the blueprint draws TEN

**Change:** `CR-143-BRC07` · **Date:** 2026-09-27 · **Version:** 2.383.5

## What the drawing says

Checked as IMAGES, per B14 rules 41/42 — `05-prototype/01 Assets Menu Blueprint.pdf`,
rendered with `10-scripts/pdf/pdf_render.py … 3 7,142`:

| Page | Figure | What it draws |
|---|---|---|
| **p7** | **Figure 1** — the Meters tab as built, desktop 1440 | `SELECT · METER # · TYPE · ROLE · SERVICE · MULT. · ASSIGNED TO · INSTALLED · STATUS · ACTIONS` — **ten columns, no size** |
| **p142** | **Figure 52** — the Meters tab remedy (`R6`) | the same ten. Its own carry-over table stamps **`Ten columns, same order — UNCHANGED`**, and its numbered legend changes only the KPI figures, the sort glyph, the row-action overflow and the pager |

**So the column is NOT drawn, and its absence is not an oversight the document
forgot to mention — the remedy drawing was the moment to add it and it
deliberately did not.** The blueprint's own convention (p2, p3, p157) is that
*"if a thing is not in a commitment card, nobody has undertaken to build it"*,
and no `AST-B-##` specification mentions a size column.

## Why it is being added anyway

PO ruling, 2026-09-27, verbatim:

> *"on asset screen can you add size - column - since it si required for billing
> it is importan we show in list vview also - add it in column seelctor also"*

That is a change to the agreement rather than a miss against it, so it is
`CR-143-BRC07` and not a defect — `13-change-process.md` §1, and the case is not
ambiguous precisely because Figure 52 stamped the ten columns `UNCHANGED` on a
dated drawing.

## The departure, stated

| | |
|---|---|
| **What was drawn** | ten columns on Meters; nine on Behind the meter |
| **What is built** | eleven on Meters, ten on Behind the meter — `Connection size` added |
| **Where it sits (Meters)** | between `SERVICE` and `MULT.` |
| **Where it sits (Behind the meter)** | between `METER` and `EXPORT CAPACITY` |
| **Sub-meters** | **NOT added.** `offersConnectionSize` refuses a size on a sub-meter, so the column could only ever draw a dash on every row for ever — hard-won law 2's mirror |
| **Heading** | `assets.col.sizeClass` — `Connection size`, the key the edit form, the add wizard and the detail Fact already use, present in all eleven catalogues. Two words, inside B14 rule 33's three |
| **Value** | the tenant's own NAME for the size class (`Water 5/8"`), never the code (`W-58`) — B14 rule 32, and the name is the only one of the two that carries a unit (CLAUDE.md hard rule 3) |
| **Empty** | `AssetDash` — the registry's own em dash, the one `INSTALLED` draws |

**Why between SERVICE and MULT.** The base charge resolves *service → account
type → size class* (`BR-RAT-108`, R3 of the R1–R7 chain), so the two facts that
pick the price sit together, and `MULT.` — which multiplies a metered quantity —
stays beside the reading columns. The drawing does not speak to the position,
so this is our judgment and it is written down rather than inferred.

**Why Behind the meter too.** CLAUDE.md's fire paragraph: the size class PICKS
the charge and the COUNT multiplies it — one 6" line is `$60.00`, one 2" line
`$12.00`. A fire line is a behind-the-meter asset, so that tab is where the size
IS the price.

## What did NOT change

The ten drawn columns, their order, their headings, the KPI strip, the toolbar,
the filters, the pager and the audit line are all untouched. Gaps 4–7 of screen
01's gap table stay blocked by the PO's 2026-09-12 ruling and are not touched
here.

## One consequence worth stating

A clerk who has **never** opened the `▦` chooser sees `Connection size` straight
away. A clerk who has customised their columns has a stored preference in
`user_preferences` under `table.S49.columns`, and `columnsFromPreference` keeps
only the keys that preference names — so the new column arrives **hidden** for
them until they tick it on or press Reset. That is the shared kit's existing,
ruled behaviour for every list in the product; changing it would touch 54 lists
at once, which is exactly the risk the PO ruled out of an Assets pass on
2026-09-12 (*"It's the right fix and it touches 54 lists at once. That risk
doesn't belong inside an Assets pass"*). It is recorded here rather than fixed.

## Proof

`07-frontend/src/features/assets/AssetSizeColumn.dom.test.tsx` — seven cases,
shown RED twice before green (the column removed; and the cell printing the
code instead of the name).
