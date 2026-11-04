// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-003 (S16 guided add: one premise and its first units)
//           Screens: S16 / PRM-07, entered from S14 "+ New premise"
// Change:   CR-177-BRC10 (2026-10-09) — Add a premise, REDESIGNED. The screen
//           lives in `./addPremise/AddPremisePage.tsx`; this file keeps the
//           route's import (`App.tsx`, `premises/new`) and nothing else.
// ───────────────────────────────────────────────────────
//
// ⛔ **THE FOUR-MODE WIZARD THAT STOOD HERE IS GONE (PO 2026-10-09).** Its step
// 1, *How many?*, offered *One premise*, *Premises CSV*, *Units pattern* and
// *Units CSV*. The PO, verbatim: *"our mistake please remove how many step …
// there is seperate improt fucntion for premsies bulk import so step 1 how many
// not required"*. Blast radius, measured before removing (2026-10-09):
//
//   · `?mode=premises_csv` / `?mode=units_csv` — re-pointed to the five-stage
//     Import runner on 2026-08-21 (`DEF-520`, `meteringShared.PREMISES_IMPORT_
//     ROUTE` / `UNITS_IMPORT_ROUTE`); NOTHING linked to them any more.
//   · `?mode=units_pattern` — `+ New unit` moved to `AddUnitsWizard` on
//     2026-09-09 (`CR-089` wave E), which builds its own `units_pattern`
//     request; NOTHING linked to it any more. (`AddUnitsWizard` imported
//     `PATTERN_UNIT_CAP` and `patternTotal` from here until the Add units
//     redesign, `CR-176-BRC10`, the same day; nothing imports them now.)
//   · `PREMISES_ADD_ROUTE` (`/premises/new`) is still the door from the
//     Premises page head and the empty state; it now opens on Property.
//
// The importer endpoints stay: Import and Add units use them.

import { AddPremisePage } from "./addPremise/AddPremisePage";

/** The route's element (`App.tsx` — `premises/new`). */
export const AddPremisesWizard = AddPremisePage;
