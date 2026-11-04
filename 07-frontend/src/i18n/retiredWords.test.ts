// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-6422 — eight clerk-facing strings still said "the register"
//          after the PO ruled on 2026-09-23 that it appears in no clerk-facing
//          string ("The register" is our internal name for a list; the clerk
//          knows each list by its own word — Premises, Accounts, Move-ins).
//          The move-in job page opened with "← The register".
// ───────────────────────────────────────────────────────
//
// `usEnglishCatalogue.test.ts` checks SPELLING; nothing checked VOCABULARY, so a
// word the PO retired stayed in the catalogue with every test green.
//
// ⚠ SCOPED TO `customers.*`, AND THE SCOPE IS STATED RATHER THAN IMPLIED (law 7:
// a check must say what it skips). The meter REGISTER — the dial a reading is
// taken from — is a real thing a clerk reads and is not the retired sense, so
// the pattern is the LIST sense: "the register", "this register" meaning a
// list, or a bare "Register" title. `ALLOWED` names every customers.* key that
// uses the meter sense, so a new one has to be looked at before it passes.
import { describe, expect, it } from "vitest";

import en from "./locales/en.json";

/** customers.* keys whose "register" is the METER's register, not a list. */
const ALLOWED = new Set([
  "customers.move.capture.estimateWhy",
  "customers.move.capture.noPrior",
  "customers.move.captured.refused.consecutive_estimate_cap_reached",
  // `DEF-CUS-6362` — the move-in's readings table column (PO-approved header,
  // the meter's register). `customers.moveIn.assets.hint` and
  // `customers.moveIn.start.metersHint` left with the two-table step.
  "customers.moveIn.reads.col.register",
  // ⛔ **`customers.moveOut.date.metersHint` LEFT THIS LIST ON 2026-09-24 WITH
  // THE KEY ITSELF (`DEF-CUS-6477`).** It was the move-out's grey note under the
  // meter list — *"Listed so you can see which registers are left unread…"* —
  // and the PO ruled the whole sentence out as rationale, which B14 rule 33 puts
  // at ZERO words on screen.
  //
  // ⚠ **THE SECOND ASSERTION BELOW IS WHAT FOUND IT, AND THAT IS THE POINT OF
  // HAVING IT.** An allow list naming a key that no longer exists is a claim
  // about nothing — it would have sat here quietly permitting a word in a key
  // that had gone. It went red the moment `i18n_fanin.py` retired the key, named
  // the key, and cost one line to clear. **A guard that also guards its own allow
  // list is the difference between a check and a decoration** — hard-won law 7's
  // *incapable of failing* shape, caught in the one place it can be caught.
  "customers.moveRecord.chip.unread_one",
  "customers.moveRecord.chip.unread_other",
  "customers.moveRecord.owed.allRead",
  "customers.moveRecord.owed.demandRegister",
  "customers.moveRecord.reads.register",
  "customers.import.unavailable.body",
]);

describe("DEF-CUS-6422 — 'register' is not a word a clerk reads in customers.*", () => {
  it("no customers.* value outside the meter-sense allow list says register", () => {
    const offenders = Object.entries(en as Record<string, string>)
      .filter(([key]) => key.startsWith("customers.") && !ALLOWED.has(key))
      .filter(([, value]) => /\bregister/i.test(value))
      .map(([key, value]) => `${key} = ${value}`);
    expect(offenders).toEqual([]);
  });

  it("the allow list names only keys that still exist and still say register", () => {
    const catalogue = en as Record<string, string>;
    const stale = [...ALLOWED].filter((key) => !/\bregister/i.test(catalogue[key] ?? ""));
    expect(stale).toEqual([]);
  });
});
