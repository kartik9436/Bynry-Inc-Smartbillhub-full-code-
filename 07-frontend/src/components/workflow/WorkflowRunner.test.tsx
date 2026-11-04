// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — the ETL runner shell and its stage bar
// Rules:    BR-SHL-018 (rail semantics) · BR-SHL-044 (one page header) ·
//           B14 rule 4 (`Verb →` advances, `Verb ✓` commits) ·
//           B14 rule 6 (danger tier on a destructive commit)
// Impacts:  src/components/workflow/{WorkflowRunner,StageBar}.tsx
// ───────────────────────────────────────────────────────
//
// Prior-run conventions: markup is asserted on `react-dom/server` static output
// and the i18next singleton is imported for its side effect, exactly as
// `WizardFrame.test.tsx` next door does. Clicking is a browser question and is
// out of scope for a static render.
//
// ⚠ THE POINT OF THIS FILE IS THE **TWO KINDS**. A kit proved with one kind is
// a component with extra steps: every one of these assertions runs over
// `premises` AND `units`, and the two-kinds test asserts they differ in exactly
// the places a kind is allowed to differ — kicker, blurb, exit route — and
// nowhere else.
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18n from "@/i18n"; // the i18next singleton with the eleven catalogues

import { WorkflowRunner } from "./WorkflowRunner";
import { WORKFLOW_KINDS, WORKFLOW_STAGES, WRITING_STAGE, type WorkflowKind } from "./kinds";

const noop = () => undefined;

function render(kind: WorkflowKind, stage: number, reached = stage): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <WorkflowRunner
        kind={kind}
        stage={stage}
        reached={reached}
        onStageChange={noop}
        headerAction={<button type="button">Save mapping as template</button>}
        onBack={noop}
        onAdvance={noop}
        advanceDisabled={false}
      >
        <p>stage body</p>
      </WorkflowRunner>
    </MemoryRouter>,
  );
}

const KINDS: [string, WorkflowKind][] = [
  ["premises", WORKFLOW_KINDS.premises],
  ["units", WORKFLOW_KINDS.units],
];

/** Static markup escapes the copy; the catalogue does not. */
function unescaped(html: string): string {
  return html
    .replaceAll("&#x27;", "'")
    .replaceAll("&quot;", '"')
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">");
}

describe("DEF-624 — the RESULT stage does not print the EXTRACT blurb", () => {
  /**
   * ⛔ `WORKFLOW_STAGES` declares `blurbKey: null` TWICE — index 0, where stage
   * 1 borrows the kind's own sub-line, and index 4, the receipt, which has
   * none. The runner coalesced both to `kind.extractBlurbKey`, so under
   * *"Loaded. Here's the receipt."* it printed *"Upload the file. Nothing is
   * written until you commit at stage four."* — AFTER the write, on every
   * target.
   *
   * ⚠ The test directly above this one is why it survived: it asserts that
   * every key EXISTS, and a fallback between two keys that both exist passes
   * it by construction. CR-023's browser walkthrough stopped at stage 4 and
   * never reached the receipt. So the check that was missing is not "does the
   * key resolve" but "is this stage showing SOMEBODY ELSE'S sub-line".
   */
  it("stage 5 shows no sub-line at all", () => {
    const html = unescaped(render(WORKFLOW_KINDS.premises, 5));
    const extractBlurb = i18n.t(WORKFLOW_KINDS.premises.extractBlurbKey);
    expect(extractBlurb.length).toBeGreaterThan(0);
    expect(html).not.toContain(extractBlurb);
  });

  it("stage 1 still shows the KIND's own sub-line — the fallback that IS wanted", () => {
    const html = unescaped(render(WORKFLOW_KINDS.premises, 1));
    expect(html).toContain(i18n.t(WORKFLOW_KINDS.premises.extractBlurbKey));
  });

  it("the middle stages still show their OWN sub-line", () => {
    for (const stage of [2, 3, 4]) {
      const declared = WORKFLOW_STAGES[stage - 1].blurbKey;
      expect(declared, `stage ${stage} declares no blurb`).not.toBeNull();
      // ⚠ `renderToStaticMarkup` escapes the copy — stage 3's blurb contains
      // an apostrophe and arrives as `don&#x27;t`. Comparing raw catalogue
      // text against raw markup fails on the punctuation rather than on the
      // thing under test, so the entities come back out first.
      expect(unescaped(render(WORKFLOW_KINDS.premises, stage))).toContain(
        i18n.t(String(declared)),
      );
    }
  });
});

describe("CR-023 · the runner is ONE implementation, `kind` parameterised", () => {
  it("the catalogue resolves every key the stage table names", () => {
    // G27 checks LITERAL `t("…")` calls and cannot see `t(stage.titleKey)`, so
    // the dynamic half is asserted here. Without this, a key typed into the
    // stage table renders its own name as a heading — DEF-282's exact shape,
    // three times in one day.
    for (const stage of WORKFLOW_STAGES) {
      for (const key of [stage.labelKey, stage.titleKey, stage.blurbKey, stage.advanceKey]) {
        if (key === null) continue;
        expect(i18n.exists(key), `${key} resolves in no catalogue`).toBe(true);
      }
    }
    for (const [, kind] of KINDS) {
      for (const key of [
        kind.kickerKey,
        kind.returnLabelKey,
        kind.extractBlurbKey,
        kind.targetLabelKey,
        kind.exitLabelKey,
        kind.nextNoteKey,
      ]) {
        expect(i18n.exists(key), `${key} resolves in no catalogue`).toBe(true);
      }
    }
  });

  it.each(KINDS)("%s · the runner's promise is printed under the title", (_name, kind) => {
    const html = render(kind, 1);
    expect(html).toContain("Five stages · nothing is written until you commit at stage four.");
  });

  it.each(KINDS)("%s · the rail draws five numbered stages", (_name, kind) => {
    const html = render(kind, 1);
    for (const label of ["Extract", "Transform", "Validate", "Load", "Result"]) {
      expect(html).toContain(label);
    }
    for (let n = 1; n <= 5; n++) {
      expect(html).toContain(`data-workflow-stage="${n}"`);
    }
  });

  it.each(KINDS)("%s · the WRITING stage is marked as the writing stage", (_name, kind) => {
    // r10 draws five identical steps under a promise that names stage four.
    // This is the assertion that the strip points at the stage the sentence
    // means — and it is the one thing on the rail r10 does not have.
    const html = render(kind, 1);
    const writes = [...html.matchAll(/data-writes="true"/g)];
    expect(writes.length, "exactly one stage writes").toBe(1);
    expect(WRITING_STAGE).toBe(4);
    // The mark sits on stage 4's own button, not on some other row.
    const stage4 = html.slice(html.indexOf('data-workflow-stage="4"'));
    expect(stage4.slice(0, 200)).toContain('data-writes="true"');
  });

  it.each(KINDS)("%s · the footer primary NAMES ITS DESTINATION", (_name, kind) => {
    // B14 rule 4: `Verb →` advances and `Verb ✓` commits. A button reading
    // "Continue" on four different stages tells a user nothing about where the
    // fourth one goes — which matters most on the one that writes.
    expect(render(kind, 1)).toContain("Transform →");
    expect(render(kind, 2)).toContain("Validate →");
    expect(render(kind, 3)).toContain("Load →");
    expect(render(kind, 4)).toContain("Commit load ✓");
  });

  it.each(KINDS)("%s · the commit that WRITES takes the danger tier", (_name, kind) => {
    // B15 §9 note 4 — "`Commit load ✓` writes; `Roll back this run` reverses.
    // Both qualify" for B14 rule 6. r10 draws it as an ordinary primary; where
    // r10 and a ratified rule disagree, the rule wins with the divergence
    // stamped. `data-variant` is the Button's own contract, so this asks about
    // INTENT rather than about colour.
    const load = render(kind, 4);
    expect(load).toContain('data-variant="danger"');
    expect(load).not.toContain('data-variant="primary"');
    // …and the three that only navigate do NOT.
    for (const stage of [1, 2, 3]) {
      const html = render(kind, stage);
      expect(html).toContain('data-variant="primary"');
      expect(html).not.toContain('data-variant="danger"');
    }
  });

  it.each(KINDS)("%s · stage 1's back action CANCELS and stage 2's steps back", (_name, kind) => {
    // B14 rule 1: a header `←` names where it EXITS; inside a stepper the
    // footer's `← Back` means only "previous step". Stage 1 has no previous
    // step, so its secondary is Cancel and never a Back that goes nowhere.
    expect(render(kind, 1)).toContain("Cancel");
    expect(render(kind, 2)).toContain("← Back");
  });

  it.each(KINDS)("%s · stage 5 renders NO advance footer", (_name, kind) => {
    // The Result stage's actions are about the RUN, not the flow, and live
    // beside the receipt. `advanceKey: null` declares the absence.
    const html = render(kind, 5);
    expect(html).not.toContain('data-workflow="footer"');
    expect(WORKFLOW_STAGES[4].advanceKey).toBeNull();
  });

  it.each(KINDS)("%s · BR-SHL-018 — an upcoming stage is not navigation", (_name, kind) => {
    // Completed steps click BACK; forward is only via a validated advance.
    // r10 wires every step to a jump handler, which would let a click on 4 skip
    // straight to the writing stage from stage 1.
    const html = render(kind, 2, 2);
    const stage4 = html.slice(html.indexOf('data-workflow-stage="4"'));
    expect(stage4.slice(0, 300)).toContain("disabled");
    const stage1 = html.slice(html.indexOf('data-workflow-stage="1"'));
    expect(stage1.slice(0, 300)).not.toContain("disabled");
  });

  it("the two kinds differ in COPY and ROUTE and in nothing else", () => {
    // This is the deliverable, asserted: a second target costs a config object.
    const premises = render(WORKFLOW_KINDS.premises, 1);
    const units = render(WORKFLOW_KINDS.units, 1);

    expect(premises).toContain("Workflow · Premises · CSV");
    expect(units).toContain("Workflow · Units · CSV");
    expect(premises).toContain("Units and meters are separate imports.");
    expect(units).toContain("No meters are created here.");
    expect(premises).toContain('href="/premises"');
    expect(units).toContain('href="/premises/units"');

    // The SHELL is identical: same title, same promise, same five stages, same
    // footer verb. Strip the two kind-shaped attributes and the rest matches.
    const shell = (html: string) =>
      html
        .replace(/data-kind="[a-z]+"/g, "")
        .replace(/Workflow · [^<]+/g, "")
        .replace(/href="\/premises[^"]*"/g, "")
        .replace(/>[^<]*separate imports\.</g, "><")
        .replace(/>[^<]*created here\.</g, "><");
    expect(shell(premises).length).toBeGreaterThan(0);
    expect(premises).toContain("Extract, transform, validate, load.");
    expect(units).toContain("Extract, transform, validate, load.");
    expect(units).toContain("Transform →");
  });

  it("BR-SHL-044 — the runner uses the SHARED page header, not its own", () => {
    // "ONE page header for every screen, including task pages and workflows."
    // DEF-021 is what eight screens each solving this separately cost.
    const html = render(WORKFLOW_KINDS.premises, 1);
    expect(html).toContain("page-header");
    expect(html).toContain("page-header-back");
  });
});
