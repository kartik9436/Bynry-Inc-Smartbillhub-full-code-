// ── Trace ──────────────────────────────────────────────
// Change:   CR-096-BRC02 — Meter Reads, the five-stage upload wizard
// Rules:    B14 rule 3, verbatim: "Any flow with 2+ stages uses the numbered
//           step rail (clickable when complete) + a wizard-actions footer" ·
//           PO ruling 2026-09-14 Q8, verbatim "numbers"
// Impacts:  components/workflow/StageBar.tsx only.
// ───────────────────────────────────────────────────────
//
// ⚖️ **WHY THIS FILE EXISTS, AND IT IS A RULING RATHER THAN A PREFERENCE.**
//
// The Meter Reads blueprint draws the upload rail with a **tick** in every
// completed step — `[✓] Extract  [✓] Transform  [3] Validate …` — on four of
// its five stage drawings. B14 **rule 41** says the product matches the
// blueprint EXACTLY, and **rule 41's own carve-out** is a drawing that
// contradicts a signed rule. B14 **rule 3** is that signed rule, and the PO was
// asked directly which wins:
//
//   > **"numbers"**  — PO, 2026-09-14, step-1 question Q8
//
// and ruled it **product-wide**: *"Seven wizards move either way, so this is a
// product-wide answer and not a Reads one."* So the badge renders the NUMBER in
// every state, and a completed stage is told apart by its TONE.
//
// ⚠ **THE DERIVED-COUNT CASE BELOW IS OUR OWN DISCIPLINE, NOT A CLAUSE OF RULE
// 3 — SAID PLAINLY BECAUSE A FALSE CITATION IS WORSE THAN NO CITATION.** Rule 3
// is quoted in full in the Trace block above and it says *numbered* and
// *clickable when complete* and nothing about a step count; r10's own rule 3,
// its source, says the same. It was put to this lane as "rule 3's second half",
// and it is not. **It is worth a test on its own merits** — hard-won law 12's
// shape, a fact stated in one place and duplicated in another that nothing
// re-checks — so the case stays and its provenance is stated honestly.
//
// Five stages today. A hardcoded `5` passes `tsc`, passes
// every existing test and passes every gate, and is wrong the day a sixth stage
// is declared — at which point the rail draws five steps over a six-stage flow
// and nothing anywhere goes red. So the count is asserted as DERIVED: the same
// component is rendered over a three-stage list and a six-stage list, and the
// rail must follow both. A test that only ever rendered `WORKFLOW_STAGES` could
// not tell a derived count from a hardcoded one — that is the "what would make
// this check pass wrongly?" question hard-won law 7 asks, and rendering one
// fixed list is exactly the false pass it has.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { StageBar } from "./StageBar";
import { WORKFLOW_KINDS, WORKFLOW_STAGES, type WorkflowStage } from "./kinds";

const noop = () => undefined;

/** Every glyph a "completed = tick" rail could reach for. */
const TICKS = ["✓", "✔", "✅", "&#10003;", "&check;"];

function rail(stages: readonly WorkflowStage[], current: number, reached: number): string {
  return renderToStaticMarkup(
    <StageBar stages={stages} current={current} reached={reached} onSelect={noop} />,
  );
}

/** A synthetic list of N stages — the only way to prove the count is derived. */
function stagesOf(n: number): WorkflowStage[] {
  return Array.from({ length: n }, (_, i) => ({
    id: WORKFLOW_STAGES[i % WORKFLOW_STAGES.length].id,
    labelKey: WORKFLOW_STAGES[i % WORKFLOW_STAGES.length].labelKey,
    titleKey: WORKFLOW_STAGES[i % WORKFLOW_STAGES.length].titleKey,
    blurbKey: null,
    advanceKey: null,
    writes: false,
  }));
}

describe("the step rail — B14 rule 3 and PO ruling Q8", () => {
  it('a COMPLETED step shows its number, not a tick — PO 2026-09-14, "numbers"', () => {
    // Stage 5 of 5: stages 1–4 are all complete, which is the state every one
    // of the blueprint's drawings renders with a ✓.
    const html = rail(WORKFLOW_STAGES, 5, 5);
    for (const step of [1, 2, 3, 4]) {
      // The badge for a completed step carries the numeral.
      expect(html).toContain(`data-workflow-stage="${step}"`);
      expect(html).toContain(`>${step}</span>`);
    }
    for (const tick of TICKS) {
      expect(html).not.toContain(tick);
    }
  });

  it("a completed step is told apart by TONE, not by a different glyph", () => {
    const done = rail(WORKFLOW_STAGES, 5, 5);
    const untouched = rail(WORKFLOW_STAGES, 1, 1);
    // Stage 1's badge says "1" whether it is the current stage or a finished
    // one — only its state attribute and its classes move.
    expect(done).toContain(">1</span>");
    expect(untouched).toContain(">1</span>");
    expect(done).toContain('data-state="done"');
    expect(untouched).toContain('data-state="active"');
  });

  it("the step count is DERIVED from the stage list, never hardcoded", () => {
    for (const n of [3, 5, 6]) {
      const html = rail(stagesOf(n), 1, 1);
      const drawn = [...html.matchAll(/data-workflow-stage="(\d+)"/g)].map((m) => m[1]);
      expect(drawn).toHaveLength(n);
      expect(drawn).toEqual(Array.from({ length: n }, (_, i) => String(i + 1)));
    }
  });

  it("the rail numbers the real flow from 1 to its own length", () => {
    const html = rail(WORKFLOW_STAGES, 1, 1);
    const drawn = [...html.matchAll(/data-workflow-stage="(\d+)"/g)].map((m) => m[1]);
    expect(drawn).toHaveLength(WORKFLOW_STAGES.length);
    expect(drawn[drawn.length - 1]).toBe(String(WORKFLOW_STAGES.length));
  });

  it("a kind may declare the promise sentence away, and reads does", () => {
    // B14 rule 33 — rationale is zero words on screen. The blueprint lists the
    // equivalent stage-4 sentence as REMOVED: "the WRITES chip on the rail says
    // it without a sentence".
    const shared = rail(WORKFLOW_STAGES, 1, 1);
    expect(shared).toContain('data-workflow="promise"');

    const suppressed = renderToStaticMarkup(
      <StageBar
        stages={WORKFLOW_STAGES}
        current={1}
        reached={1}
        onSelect={noop}
        promise={WORKFLOW_KINDS.reads.own?.railPromise}
      />,
    );
    expect(WORKFLOW_KINDS.reads.own?.railPromise).toBeNull();
    expect(suppressed).not.toContain('data-workflow="promise"');
    // The WRITES chip is still there — it is what says it instead.
    expect(suppressed).toContain('data-writes="true"');
  });
});
