// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-020 · US-WRK-021 (EP-WRK-04) — the English a Work workforce
//           screen renders while the eleven catalogues catch up.
// Rules:    B14 rule 35 (a catalogue is written in its own language) · the
//           i18n house rule: a `t()` call carries a `defaultValue` so a screen
//           renders a SENTENCE and never a key
// Tests:    src/features/work/CrewsPage.test.tsx
// Impacts:  CrewsPage.tsx · TechnicianDetailPage.tsx · SkillsWizard.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **A LEAF MODULE, AND THAT IS THE WHOLE REASON IT EXISTS.**
//
// These two maps were first written in the screens that use them —
// `STATUS_FALLBACK` in `CrewsPage.tsx`, `PROFICIENCY_FALLBACK` in
// `TechnicianDetailPage.tsx` — and importing each from the other closed a
// CYCLE: the detail screen renders the wizard, the wizard needs the
// proficiency words, the detail screen needs the status words from the list.
//
// `WorkShell.tsx` records what that costs, in this same module, three days
// ago (`DEF-WRK-3955`): *"an import cycle in ES modules does not fail: the
// constant is simply `undefined` while the other module's body runs"* — and
// `tsc` had nothing to say about any of it. The fix there was to give the
// addresses one owner and let every screen re-export its own. This is the same
// fix for words: one file that imports NOTHING, so nothing can point back at
// it.
//
// ⚠ **AND THESE ARE FALLBACKS, NOT COPY.** The keys are the copy; a catalogue
// entry always wins. They exist so the screen reads correctly in English on
// the day it ships and a `fr-FR` tenant sees a sentence rather than
// `work.crews.status.on_shift` while the eleven catalogues are updated.

/** `Work-023`'s STATUS column, and the pill on `Work-024`'s meta line.
 *
 * Five values for one column, because a crew and a contractor are rows in the
 * same table as a person (`BR-WRK-028`) and *Crew* and *Contractor* are what
 * that row's status IS — `WS-23` draws exactly that. */
/**
 * `connections.mode` / `work_orders.mode` — HOW THE WORK IS DONE.
 *
 * ⚠ **MOVED HERE FROM `buildViews.tsx` BY `DEF-MET-6453`, AND THE DEFECT IS THE
 * REASON THIS FILE EXISTS.** `buildViews` owned the map and warned, in capital
 * letters, that *"`defaultValue: order.mode` would ship `our_crew` to a clerk's
 * screen — visible, ugly and wrong"* — and `BuildOwnerScopePanel`, five hundred
 * lines below that warning, did exactly that, because it could not IMPORT the
 * map without closing a cycle: `buildViews` mounts the panel. So the words move
 * to the leaf module, both sides read them, and there is one source rather than
 * a second opinion. `customers.newConnect.mode.*` resolves in none of the
 * eleven catalogues today, which is why the fallback is what a clerk reads.
 */
export const CONNECTION_MODE_FALLBACK: Record<string, string> = {
  our_crew: "Our crew did it",
  external: "External system",
  we_schedule: "We schedule it",
};

export const STATUS_FALLBACK: Record<string, string> = {
  on_shift: "On shift",
  off_today: "Off today",
  on_break: "On break",
  off_duty: "Off duty",
  unavailable: "Unavailable",
  crew: "Crew",
  contractor: "Contractor",
};

/** `WS-24`'s PROFICIENCY column.
 *
 * ⚠ *Not held* IS A RENDERED VALUE AND NEVER A STORED PROFICIENCY. The panel
 * lists the tenant's whole skill catalogue and marks which are held, so this
 * row is the ABSENCE of a `technician_skills` row — which is why the server
 * refuses `not_held` by name if a caller ever sends it back. */
export const PROFICIENCY_FALLBACK: Record<string, string> = {
  trained: "Trained",
  certified: "Certified",
  not_held: "Not held",
};
