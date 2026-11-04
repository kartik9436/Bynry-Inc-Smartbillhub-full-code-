// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-SHL-10001 — no multi-step screen asked before the clerk left it.
// Ruling:  PO 2026-10-07: *"(a) Popup on all 45. "Save as draft" only on the 6
//          that can keep a draft. The other 39 say "Leave without saving? ·
//          Stay""*.
// Law:     CLAUDE.md hard-won law 2 — built is not wired. A guard that one
//          new wizard does not mount is a guard that silently is not there.
// ───────────────────────────────────────────────────────
//
// **WHAT THIS PROVES, AND WHY BY SOURCE.** The guard lives in the two shells
// every multi-step staff screen is drawn in — `WizardFrame` (the numbered
// rail) and `WorkflowRunner` (the import stage bar). So the questions are:
//   1 · do both shells still mount it?
//   2 · does any OTHER file draw a step rail of its own (and so escape it)?
//   3 · do exactly the six flows the PO named offer *Save as draft* — no
//       fewer, and no seventh that quietly invents a draft store?
// A new wizard built on either shell is covered on day one; a new wizard that
// hand-rolls a rail turns question 2 red and names its file.
//
// ⚠ **THE CUSTOMER PORTAL IS OUT OF SCOPE, AND THAT IS A RECORDED JUDGMENT**
// (decision log 2026-10-07, lane LEAVE-GUARD): the ruling was made about the
// staff product's clerks; the portal's own `Stepper` flows are not walked here.
import { describe, expect, it } from "vitest";

// `import.meta.glob`, not `node:fs` — the front end's tsconfig carries no node
// types, so `readFileSync` runs under vitest and FAILS `tsc --noEmit` (the trap
// `features/integrations/holds.test.ts` documents).
const RAW = import.meta.glob(["../**/*.ts", "../**/*.tsx", "!../**/*.test.ts", "!../**/*.test.tsx"], {
  query: "?raw",
  eager: true,
  import: "default",
}) as Record<string, string>;

// Vite keys this directory's own files `./x` and the rest `../dir/x`; both
// become a path from `src/`.
const FILES = Object.entries(RAW).map(([key, text]) => ({
  path: key.startsWith("./") ? `components/${key.slice(2)}` : key.replace(/^\.\.\//, ""),
  text,
}));
const staff = FILES.filter((f) => !f.path.startsWith("portal/"));

/** Files that draw a numbered step rail of their own and are NOT one of the
 *  two shells. Each needs a reason, or this list is a hiding place. */
const OWN_RAIL_EXCEPTIONS: Record<string, string> = {
  // The runbook *Check path* wizard: built and tested, and mounted by NO route
  // (nothing imports it outside its own test) — there is no screen to guard.
  "features/runbooks/run/RunWizard.tsx": "not mounted by any route",
  // The stage bar IS the runner's rail; the runner mounts the guard.
  "components/workflow/StageBar.tsx": "drawn by WorkflowRunner, which mounts the guard",
};

const SHELLS = ["components/WizardFrame.tsx", "components/workflow/WorkflowRunner.tsx"];

/** The six — the PO's words, and the store each writes. */
const DRAFT_FLOWS = [
  "features/customers/MoveInWizard.tsx", // wizard_parks (or the request's own move-in form)
  "features/customers/NewConnectWizard.tsx", // wizard_parks
  "features/customers/TransferWizard.tsx", // wizard_parks
  "features/customers/MoveOutWizard.tsx", // wizard_parks
  "features/customers/DisconnectWizard.tsx", // wizard_parks
  "features/customers/ServiceRequestCapturePage.tsx", // the request in draft
];

describe("every multi-step staff screen asks before it is left — DEF-SHL-10001", () => {
  it("both shells mount the guard: the hook, its element and its touch", () => {
    for (const shell of SHELLS) {
      const text = FILES.find((f) => f.path === shell)?.text ?? "";
      expect(text, shell).toContain("useLeaveGuard(");
      expect(text, shell).toContain("{guard.element}");
      expect(text, shell).toContain("{...guard.touch}");
    }
  });

  it("no other staff file draws a step rail of its own", () => {
    const ownRail = staff
      .filter((f) => !SHELLS.includes(f.path))
      .filter((f) => /aria-current=\{[^}]*"step"|aria-current="step"/.test(f.text))
      .map((f) => f.path)
      .filter((p) => !(p in OWN_RAIL_EXCEPTIONS));
    expect(ownRail).toEqual([]);
  });

  it("exactly the six flows the PO named offer Save as draft", () => {
    const offering = staff
      .filter((f) => !f.path.startsWith("components/") && /\bLeaveDraft\b/.test(f.text))
      .map((f) => f.path)
      .sort();
    expect(offering).toEqual([...DRAFT_FLOWS].sort());
  });

  it("counts the screens it covers (the PO's ~45) and the draft ones (6)", () => {
    const framed = staff.filter((f) => /<WizardFrame\b/.test(f.text)).map((f) => f.path);
    const runner = staff.filter((f) => /<WorkflowRunner\b/.test(f.text)).map((f) => f.path);
    // A file can be several screens (Route + Cycle, Complaint + Service intake,
    // one import page per target); the per-screen list is in the decision log.
    expect(framed.length).toBeGreaterThanOrEqual(34);
    expect(runner.length).toBeGreaterThanOrEqual(2);
    for (const flow of DRAFT_FLOWS) {
      expect(framed, flow).toContain(flow);
    }
  });
});
