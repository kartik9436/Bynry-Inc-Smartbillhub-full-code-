# SMARTBillHub · UI & UX Rules

The binding conventions for every screen. Anything new must follow these; anything found violating them is a bug.

## Navigation
1. **Exit vs step-back.** The page header's `←` always names where it exits to ("← Payments", "← Assets"). Inside a stepper, the footer's `← Back` only means *previous step*. The two never share a label.
2. **One page header.** Every screen — including task pages and workflows — uses `.page-head`: kicker, title, optional subtitle, actions right-aligned.
3. **Steppers.** Any flow with 2+ stages uses `.br-steps` (numbered, clickable when complete) + `.wizard-actions` footer. Single forms never fake a stepper.

## Buttons
4. **Grammar.** `+ Noun` opens a creator · `Verb →` navigates/advances · `Verb ✓` commits/writes · `↑` import · `↓` download · `↗` send to external system.
5. **Sizes.** Two only: default and `.btn-sm` (12px). No inline font-sizes.
6. **Danger tier.** Destructive commits (disconnect, retire, reverse, write-off) use `.btn-danger` — outlined accent, filled on hover — never the standard primary.

## Forms
7. **Date fields.** Every date uses `.date-input` (calendar affordance, MM/DD/YYYY keyed entry, Today shortcut). Never a bare text input.
8. **Dropdowns.** All selects share one chevron style. Lists with 5+ options are searchable (type-to-filter).
9. **Multi-select.** Multiple-choice fields render as removable chips + an add control — never a wall of checkboxes.
10. **Required fields.** Marked with `.req` asterisk on the label.
11. **Consequence preview.** Any form that writes money, service state, or legal notices shows a "what this will do" summary box before its commit button.

## Tables (the list-table assembly, class `.lt`)
12. **Toolbar.** `[Search…] [All | applied-filter chips ×] [+ Filter ▾] … [▦ Columns]`. Filters display as removable chips; All is the default state.
13. **Sorting.** Column headers show ⇅; click cycles asc → desc → clear.
14. **Column selector.** ▦ icon opens show/hide checkboxes with ↑↓ reorder and Reset.
15. **Row actions.** Icons with tooltips, never text links. Max 2 visible + `…` overflow. Icon vocabulary: 👁 view · ✎ edit/note · ⟲ roll back · 🔧 fix · 🖨 print · ✉ send · ⚡ raise work · ✓ assign · − remove.
16. **Pagination.** Footer on every list table: `Showing 1–50 of N · Rows per page 50/100/200/500/1000 · ⇤ ← Page x of y → ⇥`. Page size remembered per table. Summary tables inside wizards are exempt.
17. **Empty state.** Every list has one (`.empty`): what's missing, and the action that fills it.

## Copy & layout
18. **Descriptions** cap at 66% of the content width, not half.
19. **Search placeholders** follow "Search {entities}…" per module.
20. **Table type** is one size (13.5px) everywhere; no inline overrides.
