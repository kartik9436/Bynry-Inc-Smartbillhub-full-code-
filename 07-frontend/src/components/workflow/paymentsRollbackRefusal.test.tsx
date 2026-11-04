// ── Trace ──────────────────────────────────────────────
// Change:   `06 Payments Page Blueprint.pdf` phase 1, `P1.23` — *"the refusal
//           renders, and the button does not"*. Outcome, verbatim: *"A refusal
//           nothing asserts is a refusal that rots — law 2's mirror, in the one
//           place money lands in bulk."*
// Rules:    CLAUDE.md hard rule 4 (a posted payment cannot be unwritten) ·
//           hard-won law 2 and its mirror, `DEF-CWP-3925` (a live control over
//           a door that is shut) · hard-won law 7 (a check must be able to
//           fail) · B14 rule 33 (a CONSEQUENCE before an irreversible act:
//           six words per sentence, at most two)
// Tests:    this file · 06-backend/tests/test_pay_import_target.py (the server
//           half — `rollback()` refuses the target by name)
// Impacts:  components/workflow/kinds.ts · features/metering/ImportWorkflowPage.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY THIS IS A SEPARATE FILE FROM `workflowStages.test.tsx`.** Lane P1-B
// is editing the workflow kit in the same hours (`P1.17`–`P1.19`), and two
// lanes in one file is how a pathspec commit publishes or reverts work nobody
// meant to touch (CLAUDE.md law 11). A new file collides with nothing.
//
// ⚠ **AND WHY IT ASSERTS THE RULE RATHER THAN MOUNTING THE WIZARD.** The page
// that draws the button is 4,000 lines behind a four-stage fixture, and a test
// that has to commit a whole import to look at stage 5 is a test nobody runs
// when it goes red. The decision was therefore lifted OUT of the page into
// `rollbackControlIsOffered` (B14 rule 43), which is the thing this file pins —
// plus the assertion that the page actually calls it, because a rule the page
// does not consult is hard-won law 2 wearing a helper's name.

// ⚠ READ THROUGH VITE'S OWN `?raw`, NOT `node:fs` (fixed 2026-09-22, lane
// P1-B). This app carries no `@types/node`, so `import { readFileSync } from
// "node:fs"` is `TS2307: Cannot find module 'node:fs'` — it RUNS under vitest
// and never compiles, which is how a green test file left `tsc` red on the
// branch from the hour it landed. `DataTable.test.tsx` and
// `ConfirmDialogTier.dom.test.tsx` already say so in their own words; this is
// the third file to learn it, which is CLAUDE.md law 11's closing lesson in a
// different family — the repo already owned this job.
import PAGE_SOURCE from "@/features/metering/ImportWorkflowPage.tsx?raw";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n"; // the i18next singleton with the eleven catalogues

import { RollbackNotice } from "./RollbackNotice";
import { WORKFLOW_KINDS, rollbackControlIsOffered, type WorkflowKindId } from "./kinds";

describe("P1.22/P1.23 · the payments target refuses a rollback, and draws no button", () => {
  it("the payments kind declares its rollback sentence as a REFUSAL", () => {
    expect(WORKFLOW_KINDS.payments.rollbackBody.refuses).toBe(true);
    expect(rollbackControlIsOffered(WORKFLOW_KINDS.payments)).toBe(false);
  });

  it("every OTHER kind still offers the control, so this check can fail", () => {
    // ⚠ **LAW 7's SECOND HABIT, WRITTEN OUT: what would make this check pass
    // WRONGLY?** A `rollbackControlIsOffered` that returned `false` for
    // everything would satisfy the case above and quietly remove the button
    // from six live targets. Payments is the ONLY refusal on this runner.
    const others = (Object.keys(WORKFLOW_KINDS) as WorkflowKindId[]).filter(
      (id) => id !== "payments" && id !== "reads",
    );
    expect(others.length).toBeGreaterThan(0);
    for (const id of others) {
      expect(rollbackControlIsOffered(WORKFLOW_KINDS[id]), `${id} lost its rollback`).toBe(true);
    }
  });

  it("the sentence RENDERS — a refusal a clerk cannot read is a refusal that is not made", () => {
    const html = renderToStaticMarkup(
      <RollbackNotice body={WORKFLOW_KINDS.payments.rollbackBody} action={null} />,
    );
    expect(html).toContain("A posted payment cannot be unwritten");
    // …and it says what to do INSTEAD. B14 rule 33: cutting the second
    // sentence passes every length check and makes the message useless.
    expect(html).toContain("Discard the batch");
  });

  it("and NO rollback control renders beside it", () => {
    const html = renderToStaticMarkup(
      <RollbackNotice body={WORKFLOW_KINDS.payments.rollbackBody} action={null} />,
    );
    expect(html).not.toContain("<button");
    expect(html).not.toContain("Roll back this run");
  });

  it("the notice DOES draw a control when one is passed, so the case above can fail", () => {
    // The other half of law 7. `RollbackNotice` renders whatever `action`
    // holds; if it silently dropped every action, the case above would pass
    // over a component that had stopped working for all seven other targets.
    const html = renderToStaticMarkup(
      <RollbackNotice
        body={WORKFLOW_KINDS.premises.rollbackBody}
        action={<button type="button">Roll back this run</button>}
      />,
    );
    expect(html).toContain("Roll back this run");
  });

  it("the payments sentence is nobody else's, and nobody else's is the payments one", () => {
    // `DEF-623`'s law on the eighth kind: in a kit parameterised by target, an
    // UNparameterised string is a claim about one target that every other
    // target repeats — and here it would sit above a destructive control on
    // the one pipeline where acting on it would break a hard rule.
    const ids = Object.keys(WORKFLOW_KINDS) as WorkflowKindId[];
    const sentences = ids.map((id) => WORKFLOW_KINDS[id].rollbackBody.en);
    expect(new Set(sentences).size).toBe(ids.length);
    const html = renderToStaticMarkup(
      <RollbackNotice body={WORKFLOW_KINDS.payments.rollbackBody} action={null} />,
    );
    for (const id of ids) {
      if (id === "payments") continue;
      expect(html, `payments is printing ${id}'s sentence`).not.toContain(
        WORKFLOW_KINDS[id].rollbackBody.en,
      );
    }
  });

  it("the payments sentence keeps rule 33's cap: two sentences, six words each", () => {
    const sentences = WORKFLOW_KINDS.payments.rollbackBody.en
      .split(/(?<=[.!?])\s+/)
      .filter(Boolean);
    expect(sentences.length).toBeLessThanOrEqual(2);
    for (const sentence of sentences) {
      expect(sentence.trim().split(/\s+/).length, sentence).toBeLessThanOrEqual(6);
    }
  });

  it("the PAGE actually asks the rule — otherwise this whole file tests nothing", () => {
    // ⚠ **THE WEAKEST JOINT IN THIS FILE, NAMED RATHER THAN LEFT IMPLICIT
    // (hard-won law 7: *what would make this check pass wrongly?*).** Every
    // case above passes `action={null}` ITSELF, so all of them stay green over
    // a page that draws the button regardless. What connects the rule to the
    // screen is `ImportWorkflowPage` consulting `rollbackControlIsOffered` —
    // and that is a fact about a file, so it is read as one.
    //
    // This is deliberately a source read and not a mount: reaching stage 5 of
    // a 4,000-line wizard needs the four-stage fixture that
    // `ImportLoadStage.dom.test.tsx` already owns, and a test nobody can run
    // in ten seconds is a test nobody reads when it goes red. The DOM half
    // belongs with that fixture; this is the joint.
    const code = PAGE_SOURCE.split("\n")
      .filter((line: string) => !line.trim().startsWith("*") && !line.trim().startsWith("//"))
      .join("\n");
    expect(code, "the page no longer asks whether a rollback is offered").toContain(
      "rollbackControlIsOffered(kind)",
    );
  });

  it("the seven catalogue keys the target needs are all declared", () => {
    // `P1.21`. ⚠ A target registered without them shows an EMPTY PROMISE where
    // every other target shows a sentence — and `tsc` cannot see it, because a
    // missing key is a runtime lookup rather than a type error.
    const kind = WORKFLOW_KINDS.payments;
    for (const key of [
      kind.targetLabelKey,
      kind.kickerKey,
      kind.extractBlurbKey,
      kind.nextNoteKey,
      kind.exitLabelKey,
      kind.returnLabelKey,
      kind.rollbackBody.key,
    ]) {
      expect(key, "an undeclared catalogue key").toMatch(/^workflow\.payments\./);
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/06 Payments Page Blueprint.pdf phase 1 (`P1.22` · `P1.23`)
// generated: 2026-09-22 by lane P1-A
// checklist: A✔ B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: npx vitest run src/components/workflow/paymentsRollbackRefusal.test.tsx
// exceptions: the PAGE's own use of `rollbackControlIsOffered` is asserted in
//   `ImportWorkflowPage`'s own suite rather than here — mounting the wizard to
//   reach stage 5 belongs with the fixture that already does it.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
