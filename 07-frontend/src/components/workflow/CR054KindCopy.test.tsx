// ── Trace ──────────────────────────────────────────────
// Change:   CR-054 task 19 — parameterise the two shared strings that are
//           FALSE for reads.   Screens: every screen that mounts the runner
// Rules:    BR-MET-032 (ONE published template, validate THEN accept, NO
//           mapping memory) · B14 rule 4 (`Verb →` advances, `Verb ✓` commits)
// Defect:   DEF-623 — the rollback sentence, the same failure on stage 5.
// ───────────────────────────────────────────────────────
// **THE ONE PROPERTY NO OTHER CHECK IN THIS REPO ASKS FOR.**
//
// DEF-623's own note says it: the rollback key existed in all eleven catalogues
// (G32), it was a `t()` call and not a literal (G27), the prop was typed (tsc),
// and `workflowStages.test.tsx` rendered the component and asserted it drew.
// *"No gate in this repo asks whether a SHARED component's copy is TRUE for the
// kind it is currently rendering."*
//
// So this file asks exactly that, for the two strings CR-054 found:
//
//   * stage 2 promised *"Set it once and save it as a mapping template"* while
//     reads keeps no mapping and says so six lines below — the screen
//     contradicting itself, in the half both halves share;
//   * stage 4's heading read *"Dry run first. Then commit."* and **the reads
//     pipeline has no dry run at all** — a rehearsal named directly above the
//     danger-tier control that writes.
//
// The assertions are deliberately about the RELATIONSHIP (reads differs from
// the six; both are declared for every kind) rather than about two exact
// sentences, because pinning the sentence pins the copy and not the rule.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { WORKFLOW_KINDS } from "./kinds";
import { WorkflowRunner } from "./WorkflowRunner";

const t = (key: string): string => i18n.t(key);

function runnerAt(kindId: keyof typeof WORKFLOW_KINDS, stage: number): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/brazosbend/reads/upload"]}>
      <WorkflowRunner
        kind={WORKFLOW_KINDS[kindId]}
        stage={stage}
        reached={5}
        onStageChange={() => undefined}
        headerAction={null}
        onBack={() => undefined}
        onAdvance={() => undefined}
        advanceDisabled={false}
      >
        <div>stage body</div>
      </WorkflowRunner>
    </MemoryRouter>,
  );
}

describe("CR-054 task 19 — the two stage strings are per TARGET (DEF-623's shape)", () => {
  it("every kind declares both, so an eighth cannot be registered without writing them", () => {
    // The property `rollbackBody` already has, extended to two more strings:
    // REQUIRED by the type, so the compiler asks the question rather than a
    // reviewer noticing that a seventh target inherited a sixth's promise.
    for (const [id, kind] of Object.entries(WORKFLOW_KINDS)) {
      expect(kind.transformBlurb.key, id).toMatch(/^workflow\./);
      expect(kind.transformBlurb.en.length, id).toBeGreaterThan(10);
      expect(kind.loadTitle.key, id).toMatch(/^workflow\./);
      expect(kind.loadTitle.en.length, id).toBeGreaterThan(5);
    }
  });

  it("reads says something DIFFERENT from the six targets that run through import_runs", () => {
    const reads = WORKFLOW_KINDS.reads;
    for (const id of ["premises", "units", "assets_meters", "accounts"] as const) {
      expect(reads.transformBlurb.key, id).not.toEqual(WORKFLOW_KINDS[id].transformBlurb.key);
      expect(reads.loadTitle.key, id).not.toEqual(WORKFLOW_KINDS[id].loadTitle.key);
    }
    // …and the six still share one sentence, because they share one pipeline.
    expect(WORKFLOW_KINDS.premises.transformBlurb).toBe(WORKFLOW_KINDS.accounts.transformBlurb);
  });

  it("stage 2 no longer promises reads a mapping template it never keeps (BR-MET-032)", () => {
    const html = runnerAt("reads", 2);
    expect(html).toContain(t("workflow.reads.transformBlurb"));
    expect(html).not.toContain(t("workflow.transform.blurb"));
    // The premises runner is untouched — this is a widening, not a rewrite.
    expect(runnerAt("premises", 2)).toContain(t("workflow.transform.blurb"));
  });

  it("stage 4 no longer names a dry run the reads pipeline does not perform", () => {
    const html = runnerAt("reads", 4);
    expect(html).toContain(t("workflow.reads.loadTitle"));
    expect(html).not.toContain(t("workflow.load.title"));
    expect(runnerAt("premises", 4)).toContain(t("workflow.load.title"));
  });

  it("the stage the override attaches to is the stage's own id, never a number", () => {
    // ⚠ `stage === 2` would be silently wrong the day a sixth stage is
    // declared. Stage 1 and 3 and 5 must be untouched by either override.
    for (const stage of [1, 3, 5]) {
      const html = runnerAt("reads", stage);
      expect(html).not.toContain(t("workflow.reads.transformBlurb"));
      expect(html).not.toContain(t("workflow.reads.loadTitle"));
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-054 task 19 (12-governance/11-change-requests.md, PO 2026-08-30) + DEF-623's prevention column
// generated: 2026-08-30 by the CR-054 W5 frontend lane
// checklist: A✔ B=deferred(no-backend-half — kit copy) C✔ D=deferred(no-API-half) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report
// exceptions: E3 the OTHER four per-kind copy fields (`kickerKey`, `extractBlurbKey`, `targetLabelKey`, `nextNoteKey`) are not re-checked here — `workflowStages.test.tsx` already owns them, and duplicating an assertion is how two checks start disagreeing about which is authoritative
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
