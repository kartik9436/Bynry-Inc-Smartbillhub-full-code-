# 16 · Work — component inventory

**The components the twenty-one drawn screens are built from, each defined once, as Tailwind utilities, and
mapped to the staff kit that already exists.** B14 rule 21: a new screen adds **no class to a stylesheet** —
and a utility is emitted only for a file listed in `07-frontend/src/styles/route-b-migrated.txt`, so
**`features/work/` joins that list in its first commit** or every class below renders as nothing while `tsc`
and the tests pass. Where a component already exists in the staff app, **compose it; do not fork it.**

**This is the Work module's inventory, not the portal's.** `15-portal/09-component-inventory.md` was written
for a customer surface with its own shell and brand colour; Work is a **staff** surface and inherits the staff
tokens. The two inventories share names on purpose where the thing is the same (StatusPill, DataTable,
KVList) and differ where the surface differs.

## Tokens — inherited, none added

The staff tokens in `07-frontend/src/styles/tokens.css` are the palette; the drawings use exactly four
accents on a white ground: **teal** (primary outline buttons, active tab, *On site / En route* pills, the lead
KPI figure) → `text-teal-700 border-teal-600`; **amber / brown** (the consequence box border and *At reorder*,
*Partially done*, *cert expiring*, *missing*) → `border-amber-700 text-amber-800`; **red** (danger buttons,
*Urgent*, *Unassigned*, *Required*, *Below reorder*, *out of range*, *photo required*) → `text-red-700
border-red-600`; **green** (*Published*, *Scheduled*, *On shift*, *Passed*, *In cover*, *Current*, *Yes — posts
on approval*) → `text-green-700 border-green-600`. Everything else is `text-slate-900` on white with
`border-slate-300`. Type: the shell's body face at 14 px; mono (`font-mono text-[11px] uppercase
tracking-wider text-slate-500`) for every kicker, caps header, pill and count footer — **the drawings set all
their small labels in mono caps, and that is one rule, not thirty.**

## Frames

| Component | What it is | Tailwind recipe | Staff kit |
|---|---|---|---|
| `StaffShell` | the existing shell — top bar (product · utility · Search · initials), sidebar | exists | `AppShell` |
| `WorkTabs` | the module's tab strip under the shell: **Orders · Awaiting approval · Map · Crews · Parts · Templates · Rules · Performance**; active tab has a top border and bold label | `flex border-b border-slate-300`; tab `px-4 py-2 text-sm`; active `border border-b-0 border-slate-300 -mb-px bg-white font-semibold` | the Settings tab strip (`S8`) — same component, different tabs |
| `WizardFrame` | the eight-step (or six-step) frame: step counter top-right, `Stepper`, body, `ButtonRow` | exists (`WizardFrame` with `steps` / `commitVariant`) | New Connect wizard |
| `Document` | the report — a PDF with the utility's kicker, a title, caps sections, no chrome | `max-w-[840px] mx-auto p-8 text-[13px]`; sections `border border-slate-300 mb-4` | the bill document renderer |

## Heads and navigation

| Component | Tailwind recipe | Notes |
|---|---|---|
| `PageHead` — `Kicker` (*WORK*, *WORK › TEMPLATES*, *SETTINGS › CONFIGURE › REFERENCE DATA › WORK*) · `Title` · one sentence · optional right-side button | kicker `font-mono text-[11px] uppercase tracking-wider text-slate-500`; title `text-xl font-semibold mt-1`; sentence `text-sm text-slate-600 mt-1 max-w-[70ch]` | staff `PageHeader` (kicker/title/backTo/actions) — B14 rule 32: **one sentence** |
| `MetaLine` (*221 Oak Ave · A-10688 · North · Route 1 · Normal · D. Ortiz · Today 15:30 · Scheduled*) | `text-sm text-slate-600` joined with `·` | facts only — never a control (rule 32's row-of-controls clause) |
| `Stepper` — 8 chips, active outlined teal, done plain, future grey | `flex gap-1`; chip `font-mono text-xs px-2 py-1 border border-slate-300`; active `border-teal-600 text-teal-700` | `WizardFrame.steps` |
| `Tabs` — *Overview · Checklist · Parts · Location · Customer · Audit* | as `WorkTabs`, inside a page | the record-detail tabs on S88 |
| `SegmentedControl` — **Stock register** \| Issue log | `inline-flex font-mono text-xs border border-slate-300`; segment `px-3 py-1`; active `border border-teal-600 text-teal-700 -m-px` | new — one instance (Work-025) |

## Cards, panels, tables

| Component | Tailwind recipe | Notes |
|---|---|---|
| `Card` — bordered, mono caps header row with an optional right control (*Filter by service ▾*, *Columns ▾*, a search, *Effective 01 Jan 2026*) | `border border-slate-300`; header `flex justify-between px-3 py-2 font-mono text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-300` | portal `Card` |
| `Panel` — a `Card` whose body is fields or checklist rows rather than a table (*START FROM A PACK*, *SAFETY — BEFORE YOU START*) | same shell; body `p-3` | portal `Panel` |
| `DataTable` — **B14 rule 20's one table**: 13.5 px rows, 12 px mono caps headers, right-aligned numbers, optional leading checkbox column, pills, icon actions | `w-full text-[13.5px]`; `th` `font-mono text-[11px] uppercase tracking-wider text-slate-500 text-left px-3 py-2 border-b`; `td` `px-3 py-2 border-b border-slate-200`; numeric `text-right tabular-nums` | staff `DataTable` + `FilterBar` + `ListPager`; **CR-045 toolbar (search · filter set · download) on every list** |
| `FilterBar` — search box + chip filters (*Type · all*) | `flex gap-2 p-2`; chip `text-sm border border-slate-300 px-2 py-1` | staff `FilterBar` |
| `EditableTable` — a `DataTable` with a drag handle ≡, a row number, a ✕ remove cell and an **inline add row** of inputs plus **+ Add** | handle `cursor-grab text-slate-400`; add row `flex gap-2 p-2 border-t` | new — Work-015, Work-016; the order is data (`seq`) |
| `CountFooter` — *6 templates · 4 published · 1 draft · 1 inactive* | `font-mono text-xs text-slate-600 px-3 py-2 border-t` | portal `Card` footer |
| `TotalRow` — bold last row | `font-semibold border-t-2 border-slate-400` | portal `KVList.TotalRow` |
| `KVLine` — one dense line of facts with bold values (*AST-04412 · Electric meter · … · account **A-10688***) | `text-sm`; values `font-semibold` | portal `KVList` collapsed to a line |
| `InlineFigures` — *Jobs closed **88** · First-visit completion **92%** · Avg vs estimate **−4 min*** | `text-sm`; figures `font-semibold tabular-nums` | — |

## Signals

| Component | Tones and words | Tailwind recipe |
|---|---|---|
| `StatusPill` — mono, bordered, no fill | green *Published · Scheduled · On shift · Passed · In cover · Current · On · yes* · teal *On site · En route · Off today* · amber *Draft · Partially done · At reorder · cert expiring · missing — job cannot close* · red *Unassigned · Required · Below reorder · no · 0–999* · grey *Inactive · Queued · Contractor · Superseded · Off · Optional · No — recorded only* | `inline-block font-mono text-[11px] px-1.5 py-0.5 border` + tone `border-{tone}-600 text-{tone}-700` — staff `StatusPill(tone)` |
| `PriorityPill` — *Urgent* red · *High* amber · *Normal* / *Low* grey | as `StatusPill`; always mono | the dispatcher only |
| `KPIStrip` / `KpiTile` — caps label · big figure · one sub-line; **four or five** tiles; a lead tile in teal | strip `grid grid-cols-5 border border-slate-300 divide-x`; tile `p-3`; label mono caps; figure `text-2xl font-semibold tabular-nums`; sub `text-xs text-slate-600`; lead `text-teal-700` | staff `KPIStrip` — grows to five columns |
| `Thumbnail` — ▣ IMG-8841 · 15:12, clickable | `inline-flex items-center gap-1 text-sm`; a 16 px frame glyph | new; opens the full image with taken-at and device |
| `FlagText` — *out of range*, *photo required*, *flagged* inline in red | `text-red-700` | never a block; **flag, never refuse** (`WM-35`) |
| `ChipRow` — *Backflow tester* `exp Jan 2028` | chip as `StatusPill.green` | Work-024 |
| `CheckRow` — ☐ / ☑ with a label and meta (*· 3 min*, *· photo required*) | `flex gap-2 text-sm py-1`; box `w-4 h-4 border border-slate-400` | the checklist panels and the move-out step |
| `ContactRow` — 📄 / ☎ + text | `flex gap-2 text-sm py-1` | Work-008 help & support |

## Boxes and notes

| Component | Tailwind recipe | Where |
|---|---|---|
| `ConsequenceBox` — **the box that says what pressing the button does**: amber-brown border, optional bold title (*Change effects*, *What this writes*, *Reorder*, *Certification watch*, *Audit*), one to three lines with bold consequences | `border border-amber-700 p-3 text-sm my-3`; title `font-semibold` | Work-014 · 015 · 016 · 017 · 021 · 023 · 025 · 026 · 027 · 028 · 029 · 030 · 033 — portal `ConsequenceBox`, same component |
| `NoteBar` — a small grey left-rule note under a table or a button row (*Delete is disabled because…*) | `border-l-4 border-slate-300 pl-3 text-xs text-slate-600 my-3` | portal `InfoBar`; **rule 32: no rule id or column name in it** |

## Forms and controls

| Component | Tailwind recipe | Notes |
|---|---|---|
| `FormField` — mono caps label · full-width input · optional **help line listing the allowed values** (*Queued · Scheduled · En route · On site · Complete · On hold · Cancelled*) | label `font-mono text-[11px] uppercase tracking-wider text-slate-500 mb-1`; input `w-full border border-slate-300 px-3 py-2 text-sm`; help `text-xs text-slate-600 mt-1` | staff `FormField`; the help line is the drawings' way of showing an enum — build it as a select whose options are the listed words |
| `PackCard` — a bordered tile with a title and a one-line count (*Meter exchange · 7 tasks · 3 parts · 3 readings*), one selected | `border border-slate-300 p-3 text-sm min-w-[180px]`; selected `border-teal-600`; disabled `text-slate-400` | Work-014 only |
| `Button` — three tiers, one size on these screens | primary outline `border border-teal-600 text-teal-700 px-3 py-2 text-sm` (**Continue →**, **Publish template**, **Save changes ✓**, **Raise work order ✓**, **Mark complete**) · secondary `border border-slate-400 text-slate-900` (**Save draft**, **Reassign…**, **Duplicate**) · danger `border border-red-600 text-red-700` (**Cancel order**, **Cancel work order**, **Delete**) · disabled `opacity-50 cursor-not-allowed` | staff `Button` (variant · size; `data-variant`) — **B14 rule 5: two sizes; rule 6: destructive commits are danger-tier** |
| `ButtonRow` / `ActionRow` — buttons in a row; the wizard's is *← Back · Continue → · Save draft*; a detail's ends in the danger button | `flex gap-2 mt-3` | — |
| `IconAction` — pencil ✎ (edit), eye 👁 (view), ✕ (remove) | `w-4 h-4 text-slate-500 hover:text-slate-900` | **B14 rule 15: icons for row actions** |
| `MoneyCell` — right-aligned, tabular; **2 dp** everywhere a customer could see it, **4 dp** only on the labour-rates settings screen where the stored value is being edited | `text-right tabular-nums` | staff `MoneyCell`; hard rule 2 |

## What the drawings need that the staff kit does not have yet — three things

1. **`EditableTable`** with a drag handle and an inline add row (Work-015, Work-016). Nothing in the staff app reorders rows by dragging today.
2. **`SegmentedControl`** (Work-025) — a two-segment toggle inside a page head.
3. **`Thumbnail`** with a lightbox (Work-008, Work-032, Work-033) — the staff app has never shown a captured photograph.

Everything else is composition of what exists. **Adding the three costs three files under `features/work/`
and three lines in `route-b-migrated.txt`**, and no class in any stylesheet.
