// ── Trace ──────────────────────────────────────────────
// Story:    US-MET-005 (S26 Routes · S27 Cycles — the read-only operational views)
// Change:   `DEF-GOV-10106` — THE TWO SCREENS THIS FILE HELD ARE DELETED.
// ───────────────────────────────────────────────────────
// ⚠ **`RoutesOpsPage` (S26) AND `CyclesOpsPage` (S27) ARE GONE, AND SO IS
// EVERYTHING ONLY THEY RENDERED** (the progress bar, the completeness cell, the
// chase-list panel, the cycles table, the Settings link and their helpers).
// Both had been rendered by no screen: the Meter Reads blueprint's entry 15
// put the cycles tab on `ReadCyclesTab` (server-paged, NFR-3) and entry 14
// retired Routes as a screen, `reads/routes` and `reads/cycles` now redirecting
// to it (`RedirectToReadCycles`, mounted in `App.tsx`). G40 counted both as
// dead UI. `ReadCyclesTab.test.tsx`'s entry-14 hold named this deletion as its
// step 3.
//
// What stays is the two query keys other screens still invalidate by.

export const routesQueryKey = ["routes", "ops"] as const;
export const cyclesQueryKey = ["cycles", "ops"] as const;
