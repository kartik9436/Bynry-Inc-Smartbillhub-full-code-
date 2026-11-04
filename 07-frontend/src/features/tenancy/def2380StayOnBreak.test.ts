// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-2380 — a run that finished with a broken step handed the owner
//          into the app anyway, past the reason they needed to read.
//          Screens: S114 (signup → provisioning)
// Rules:   PO 2026-09-02 verbatim: "also if it break - dont login , just keep
//          it on same screen" · BR-TEN-063 (a block's failure never rolls back
//          the rest) · C-15 (PO 2026-08-17, "soft: … tenant still opens") ·
//          BR-TEN-060 (an unwired seam is a NAMED line, not a skip) ·
//          DEF-2370 (one predicate answers "may the owner leave")
// ───────────────────────────────────────────────────────
/**
 * **THE JOB SUCCEEDING AND THE RUN SUCCEEDING ARE DIFFERENT FACTS.**
 *
 * The worker is *supposed* to finish: each block has its own transaction so one
 * failure cannot roll back the rest, and the Product Owner ruled that a short
 * block must not stop the tenant opening. So `status: "succeeded"` means *the
 * walk completed*, not *everything seeded*. `plantPhase` read the first as the
 * second, which is why `partial` almost never fired — it needed the whole JOB
 * to fail, which is the rare case rather than the ordinary one.
 *
 * RED FIRST, quoted from the run before the fix:
 *   `expected 'ready' to be 'partial'`  (case 1)
 *   `expected true to be false`          (case 2, handoverReady)
 */
import { describe, expect, it } from "vitest";

import { anyStepFellShort, handoverReady, plantPhase } from "./SignupWizard";
import type { JobRecord } from "@/api/client";
import type { SamplePlant } from "@/api/endpoints";

const PLANT = { job_id: "j1", status_url: "/jobs/j1", status: "running", total: 18 } as SamplePlant;

function job(steps: { key: string; outcome: string }[]): JobRecord {
  return {
    id: "j1",
    kind: "tenancy.sample_data_plant",
    status: "succeeded",
    progress: { done: 18, total: 18 },
    result_link: null,
    error: null,
    steps,
  } as unknown as JobRecord;
}

const SEEDED = Array.from({ length: 18 }, (_, i) => ({ key: `k${i}`, outcome: "seeded" }));

describe("DEF-2380 — a broken step keeps the owner on the screen", () => {
  it("is PARTIAL when the walk finished and a step failed", () => {
    const withBreak = SEEDED.map((s, i) => (i === 7 ? { ...s, outcome: "failed" } : s));
    const phase = plantPhase({ committed: true, plant: PLANT, job: job(withBreak), gaveUp: false });
    expect(phase).toBe("partial");
  });

  it("is PARTIAL when a step was skipped, because nothing was put in the utility either way", () => {
    const withSkip = SEEDED.map((s, i) => (i === 3 ? { ...s, outcome: "skipped" } : s));
    expect(plantPhase({ committed: true, plant: PLANT, job: job(withSkip), gaveUp: false })).toBe(
      "partial",
    );
  });

  it("is still READY when every step seeded — the working case must not become a refusal", () => {
    expect(plantPhase({ committed: true, plant: PLANT, job: job(SEEDED), gaveUp: false })).toBe(
      "ready",
    );
  });

  it("cannot invent a failure from a server that serves no step rows", () => {
    expect(anyStepFellShort(job([]))).toBe(false);
    expect(plantPhase({ committed: true, plant: PLANT, job: job([]), gaveUp: false })).toBe("ready");
  });

  it("leaves the way off the screen open — the tenant still opens (C-15)", () => {
    // `partial` withholds the AUTOMATIC hand-over and keeps the button live.
    // Disabling it would strand the owner, which the PO never asked for.
    expect(handoverReady("partial")).toBe(true);
    expect(handoverReady("seeding")).toBe(false);
  });
});
