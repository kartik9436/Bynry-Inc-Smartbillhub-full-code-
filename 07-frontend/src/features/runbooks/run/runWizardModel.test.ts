/* ══════════════════════════════════════════════════════════════════════════
 * CR-075 wave C · C4 — the Check path's ONE decision, asserted as a RULE
 * ══════════════════════════════════════════════════════════════════════════
 * Every case here asserts a rule by name, never an impression, which is the
 * plan's own definition of done for this task:
 *
 *   · `04-flows.md` §4 — a Check's rail is FOUR steps, the six without Approve
 *     and Applying;
 *   · `RBR-01` — every declared step is listed before the first one starts, and
 *     a step that did not run carries the reason it did not;
 *   · B14 rule 3 — a rail cell is navigation only where the clerk has been.
 *
 * ⚠ **THE CASE THAT MATTERS MOST IS THE EMPTY ONE**, and it is the shape
 * `DEF-RBS-4286` is filed about: hand `progressRows` no outcomes at all — which
 * is what the product can serve today — and every row must still say something.
 * A blank step is the defect this screen exists to prevent, so the assertion is
 * *no row has an empty reason AND an empty reasonKey*, over every phase.
 *
 * WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2)
 * ---------------------------------------------------
 * A `progressRows` that returned `[]` would satisfy every "no row is blank"
 * assertion vacuously — so each of those cases asserts the LENGTH against the
 * catalogue first. That is the `G5`-called-192-skips-a-pass shape, one register
 * down, and it is the only false pass this file has.
 * ══════════════════════════════════════════════════════════════════════════ */
import { describe, expect, it } from "vitest";

import {
  CHECK_STEPS,
  STEP_NEVER_REACHED_KEY,
  STEP_WAITING_KEY,
  currentStep,
  progressRows,
  railCells,
  scopeStartKey,
  stepsFinished,
} from "./runWizardModel";
import type { RunPhase, StepCatalogueEntry, StepOutcome } from "./runWizardModel";

/** Runbook 1's own ten, in `configuration_check.py`'s `STEP_LABELS` order. */
const TEN: StepCatalogueEntry[] = [
  { key: "services_and_units", label: "Services and units" },
  { key: "reference_data", label: "Reference data" },
  { key: "tax", label: "Tax" },
  { key: "plans_in_force", label: "Plans in force" },
  { key: "rate_coverage", label: "Rate coverage" },
  { key: "account_chain", label: "Account chain" },
  { key: "meters", label: "Meters" },
  { key: "reads_and_windows", label: "Reads and windows" },
  { key: "documents", label: "Documents" },
  { key: "books", label: "Books" },
];

const ALL_PHASES: RunPhase[] = ["scoping", "checking", "checkFailed", "review", "done"];

describe("04-flows.md §4 — a Check's wizard is four steps, not six", () => {
  it("is Scope, Checking, Review, Done — the Action rail without Approve and Applying", () => {
    expect([...CHECK_STEPS]).toEqual(["scope", "checking", "review", "done"]);
    // The two a Check skips, named so a lane adding them meets this by name.
    expect(CHECK_STEPS).not.toContain("approve");
    expect(CHECK_STEPS).not.toContain("applying");
  });

  it("draws four rail cells in every phase, numbered 1 to 4", () => {
    for (const phase of ALL_PHASES) {
      const cells = railCells(phase);
      expect(cells, phase).toHaveLength(4);
      expect(cells.map((c) => c.position)).toEqual([1, 2, 3, 4]);
    }
  });

  it("marks exactly one cell current, and it is the phase's own step", () => {
    for (const phase of ALL_PHASES) {
      const cells = railCells(phase);
      const current = cells.filter((c) => c.state === "current");
      expect(current, phase).toHaveLength(1);
      expect(current[0].id).toBe(currentStep(phase));
    }
  });

  it("B14 rule 3 — a cell is clickable only where the clerk has already been", () => {
    const cells = railCells("done");
    expect(cells.filter((c) => c.clickable).map((c) => c.id)).toEqual([
      "scope",
      "checking",
      "review",
    ]);
    // Nothing forward is ever navigation: from Scope, nothing is clickable at
    // all, so a clerk cannot jump to a report that does not exist yet.
    expect(railCells("scoping").some((c) => c.clickable)).toBe(false);
  });

  it("a failed check leaves Checking CURRENT rather than ticking it", () => {
    // `RBS-005.8`'s frame: ✓ Scope → 2 Checking (accent) → 3 Review. A tick on
    // a step that broke is the same lie as a Done row with no record behind it.
    const cells = railCells("checkFailed");
    expect(cells.find((c) => c.id === "checking")?.state).toBe("current");
    expect(cells.find((c) => c.id === "scope")?.state).toBe("done");
  });
});

describe("RBR-01 — every step is listed before the first one starts", () => {
  it("draws all ten of runbook 1's steps while nothing has run", () => {
    const rows = progressRows(TEN, {}, "scoping");
    expect(rows).toHaveLength(TEN.length);
    expect(rows.map((r) => r.label)).toEqual(TEN.map((s) => s.label));
  });

  it("shows the clerk-facing label and never the step key (B14 rule 31)", () => {
    const rows = progressRows(TEN, {}, "checking");
    for (const row of rows) {
      expect(row.label).not.toBe(row.key);
      expect(row.label).not.toContain("_");
    }
  });
});

describe("RBR-01 — a step that did not run carries the reason it did not", () => {
  it.each(ALL_PHASES)("no row is blank in phase %s, with NO outcomes served", (phase) => {
    // ⚠ THE `DEF-RBS-4286` CASE. An empty outcome map is what the product can
    // serve today: a run records no per-step outcome anywhere. Every row must
    // still say something — and the rule's own words are *a step that DID NOT
    // RUN carries the reason it did not*, so the one step that IS running is
    // speaking by its state and needs no sentence. Every other row needs one.
    const rows = progressRows(TEN, {}, phase);
    expect(rows, "an empty list would satisfy the loop below vacuously").toHaveLength(10);
    for (const row of rows) {
      const speaks = row.reason !== null || row.reasonKey !== null || row.state === "current";
      expect(speaks, `${phase} · ${row.key} drew a blank step`).toBe(true);
    }
    // …and *current* is not a way to be silent ten times over: at most one row
    // may lean on it, which is what makes the assertion above worth making.
    expect(rows.filter((r) => r.state === "current").length).toBeLessThanOrEqual(1);
  });

  it("says Never reached once the run has stopped, and waiting while it runs", () => {
    const halfway: Record<string, StepOutcome> = {
      services_and_units: { state: "done", detail: "11 services" },
      reference_data: { state: "done", detail: "2 series" },
    };
    const running = progressRows(TEN, halfway, "checking");
    const stopped = progressRows(TEN, halfway, "checkFailed");

    // Running: the first unrecorded step is CURRENT and says nothing extra;
    // the ones behind it are waiting their turn.
    expect(running[2].state).toBe("current");
    expect(running[2].reasonKey).toBeNull();
    expect(running[3].reasonKey).toBe(STEP_WAITING_KEY);

    // Stopped: nothing is current any more, and every unrecorded step says the
    // run never got that far, rather than sitting blank.
    expect(stopped.some((r) => r.state === "current")).toBe(false);
    for (const row of stopped.slice(2)) {
      expect(row.reasonKey, row.key).toBe(STEP_NEVER_REACHED_KEY);
    }
  });

  it("a step the run FAILED carries the run's own sentence, verbatim", () => {
    const failed: Record<string, StepOutcome> = {
      services_and_units: { state: "done", detail: "1,004" },
      reference_data: {
        state: "failed",
        reason: "Could not read protections. Nothing was changed.",
        detail: "stopped",
      },
    };
    const rows = progressRows(TEN, failed, "checkFailed");
    expect(rows[1].state).toBe("failed");
    expect(rows[1].reason).toBe("Could not read protections. Nothing was changed.");
    // OURS is a KEY and the SERVER'S is bytes; folding one into the other would
    // make `reason`'s promise false and leave the next reader unable to tell
    // which kind of sentence they hold.
    expect(rows[1].reasonKey).toBeNull();
    expect(rows[2].reason).toBeNull();
    expect(rows[2].reasonKey).toBe(STEP_NEVER_REACHED_KEY);
  });

  it("a step with NO record is never Done, in any phase", () => {
    for (const phase of ALL_PHASES) {
      const rows = progressRows(TEN, { tax: { state: "done" } }, phase);
      const done = rows.filter((r) => r.state === "done").map((r) => r.key);
      expect(done, phase).toEqual(["tax"]);
    }
  });

  it("a step that finished cleanly puts its sentence on the DETAIL line, not the reason", () => {
    const rows = progressRows(TEN, { tax: { state: "done", detail: "3 regions", reason: "x" } }, "done");
    const tax = rows.find((r) => r.key === "tax");
    expect(tax?.detail).toBe("3 regions");
    expect(tax?.reason).toBeNull();
  });
});

describe("the bar counts steps, never a clock", () => {
  it("counts finished and skipped steps and nothing else", () => {
    const rows = progressRows(
      TEN,
      {
        services_and_units: { state: "done" },
        reference_data: { state: "skipped", reason: "Nothing configured" },
        tax: { state: "failed", reason: "Could not read" },
      },
      "checkFailed",
    );
    expect(stepsFinished(rows)).toBe(2);
  });
});

describe("the Scope button says what is about to happen", () => {
  it("uses the sheet's own words above one subject", () => {
    expect(scopeStartKey(1004)).toBe("runbooks.run.scope.start");
  });

  it("does not print 'Check these 1' for a one-subject Check", () => {
    // Runbook 1 declares subject_type = tenant and resolves to ONE subject —
    // *This utility* — so the sheet's `Check these 1,004 →` taken literally
    // renders a count that carries no information.
    expect(scopeStartKey(1)).toBe("runbooks.run.scope.startOne");
  });
});
