# src/components — the FE-01..21 shared component registry

Every shared component in this app is one of the 21 rows in
`04-docs/02-decisions/13-component-registry.md` §1 (FE-01 AppShell … FE-21
TemplateDesigner), with `13a-screen-component-map.md` proving every screen
resolves to these parts plus configuration.

Rules (B8 + B13 checkpoint protocol):

- ONE implementation per registry row — e.g. ONE `DataTable` (FE-02) implements
  the IS-5 capability row; ONE `ConfirmDialog` (FE-04) implements IS-6.
- Components are built story-by-story through their packets, in the waves shown
  in B13 — nothing is hand-added here outside the registry.
- A feature story may not build on a component whose B13 status cell is not ✅.

This directory is intentionally empty in the W0 scaffold.

## Which control do I reach for? — the two comboboxes

B14 rule 43's obligation runs both ways: **before building a piece of UI, look
for the component.** These two look alike and are not interchangeable, and not
knowing that is what `DEF-PAY-6319` cost — three features hand-rolled a
two-field "search box + select" pattern because the kit appeared to have
nothing.

| You have… | Use | Why not the other |
|---|---|---|
| A list the browser ALREADY HOLDS, and it is long (B14 rule 8: 5+ options are searchable) | `SearchSelectField` (in `FormModal.tsx`) | It filters in memory. It has two things to say — *here are the options* and *No matching options* |
| A search that runs on the SERVER (`IS-3`: debounced, from two characters) | `RemoteSearchSelectField` | A server search has **five** states, and four of them are not options: typed too little · searching · **the search itself failed** (`BR-SHL-020`, the one support can act on) · nothing matched that term · matches. Drawing the last two as one empty list is a regression, not a simplification |

`RemoteSearchSelectField` takes its four sentences from its HOST (B14 rule 35 —
a catalogue is written in its own language), so adopting it moves no catalogue
key. `features/payments/paymentsShared.tsx`'s `AccountPickerFields` is the
worked example, and `customers/accountFinder.tsx` and
`metering/OwnerAccount.tsx` are the two screens still hand-rolling the old
pattern.

⚠ **THE LAST LINE OF THE SECTION ABOVE IS FALSE AND IS FILED, NOT FIXED.** This
directory has not been "intentionally empty in the W0 scaffold" for a long time
— it holds over a hundred files, and the 21-row registry it describes is not the
shape of the kit any more. `DEF-SHL-6333`.
