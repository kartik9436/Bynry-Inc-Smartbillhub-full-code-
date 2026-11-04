// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  the uniform correction verbs. PO ruling 2026-09-17, shown a table of
//          what each of the five priced objects does today: *"please fix all
//          these"*.
// Defects: DEF-RAT-5709 — a discount cannot be edited at all, not even a draft
//          nobody has submitted.
// Rules:   BR-RAT-1016 (the three verbs) · BR-RAT-104 (the shape) · BR-RAT-077
//          / BR-RAT-109 (the approval workflow, untouched) · BR-RAT-078
//          (enrolments survive versioning) · CLAUDE.md hard rule 4 · hard-won
//          law 2 (a verb with no way in does not exist) · B14 rule 33
// Screens: DIS-02 step 4 · CHG-01.discount's action cluster
// ───────────────────────────────────────────────────────
/**
 * **WHICH ACT A SAVE IS, AND WHETHER THE OPERATOR CAN REACH IT.**
 *
 * The backend now has three verbs where it had one. A server verb with no
 * control is a verb that does not exist (hard-won law 2), and the mirror is
 * just as costly: a control offered in a state the server refuses is a road
 * that ends. So this suite asks both questions — is the door THERE when the
 * verb is legal, and is it ABSENT when it is not.
 *
 * ⚠ **THE CHOICE ITSELF IS THE RISK AND IS WHY `discountVerb` IS PURE AND
 * EXPORTED.** *A new price from a date* and *that figure was always wrong*
 * produce different history. A branch chosen inside a component is a branch
 * nobody tests for the case that does not render, and this one decides between
 * minting a version and superseding one.
 *
 * ── PROVED RED FIRST (hard-won law 7), through `vitest`, the harness that runs
 * ── them. What each printed before the change ──────────────────────────────
 *
 * * every case in the first group —
 *
 *       SyntaxError: The requested module './DiscountWizard' does not provide
 *       an export named 'discountVerb'
 *
 * * `a live version offers the correction door` —
 *
 *       TestingLibraryElementError: Unable to find an accessible element with
 *       the role "button" and name "Fix this version"
 *
 * * `a draft offers no correction door` — with `discountCorrectable` returning
 *   true for any version at all, which is the obvious first draft:
 *
 *       AssertionError: expected true to be false
 *
 * * `the correction's window is refused on the control` — with both
 *   `disabled={props.correcting}` removed from the two date pickers, which is
 *   the state the screen was in for one commit:
 *
 *       AssertionError: expected '// ── Trace ──…' to contain
 *       'disabled={props.correcting}'
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";

import { discountCorrectable } from "./DefinitionDetailPage";

// ⚠ **`DiscountWizard.tsx` IS RETIRED (CR-166-BRC10 round 3 task 7).** The New
// door opens `discountForm/NewDiscountWizard.tsx` and the Edit door
// `discountForm/EditDiscountForm.tsx`; the cases that read the old wizard's
// source or its exports went with it. What they guarded now lives in
// `discountForm/*.test.ts(x)`: the three edit verbs are the three *What to
// change* choices (`EditDiscountForm.dom.test.tsx`), and a correction's window
// is drawn as facts, never as live boxes (image 34).

// ══════════════════════════════════════════════════════════════════════════
// Where the correction door is offered
// ══════════════════════════════════════════════════════════════════════════

describe("BR-RAT-1016 · the correction door appears only where the verb is legal", () => {
  it("a live version offers it", () => {
    expect(discountCorrectable("active")).toBe(true);
  });

  it("a draft does not — it is edited in place", () => {
    expect(discountCorrectable("draft")).toBe(false);
  });

  it.each(["pending_approval", "scheduled", "rejected"])(
    "a filing that never went live does not (%s)",
    (status) => {
      // It has priced nothing, so there is no recorded figure to correct: it is
      // withdrawn and re-filed.
      expect(discountCorrectable(status)).toBe(false);
    },
  );

  it("a superseded row does not — it is the audit artefact", () => {
    expect(discountCorrectable("superseded")).toBe(false);
  });

  it("a discount with no version at all does not", () => {
    expect(discountCorrectable(null)).toBe(false);
    expect(discountCorrectable(undefined)).toBe(false);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// The copy
// ══════════════════════════════════════════════════════════════════════════

describe("BR-RAT-1016 · the discount copy obeys its caps", () => {
  const sentences = (text: string) =>
    text
      .split(/(?<=[.!?])\s+/)
      .map((one) => one.trim())
      .filter((one) => one !== "");

  it("every new refusal and hint is six words or fewer per sentence, two at most", () => {
    for (const key of [
      "rating.discounts.edit_not_a_draft",
      "rating.discounts.edit_already_submitted",
      "rating.discounts.correct_draft",
      "rating.discounts.correct_not_in_force",
      "rating.discounts.already_corrected",
      "rating.discounts.correction_reason",
      "rating.discounts.correction_empty",
      "rating.discountWizard.correctionReasonHelp",
      "rating.discountWizard.correctionIssued",
    ]) {
      const text = (en as Record<string, string>)[key];
      expect(text, `${key} is missing from the catalogue`).toBeTruthy();
      const parts = sentences(text);
      expect(parts.length, key).toBeLessThanOrEqual(2);
      for (const part of parts) {
        expect(part.replace(/[.!?]$/, "").split(/\s+/).length, `${key}: "${part}"`)
          .toBeLessThanOrEqual(6);
      }
    }
  });

  it("a label is three words or fewer and is not a sentence", () => {
    for (const key of [
      "rating.definition.action.correct",
      "rating.discountWizard.correctionReasonLabel",
    ]) {
      const text = (en as Record<string, string>)[key];
      expect(text.split(/\s+/).length, key).toBeLessThanOrEqual(3);
      expect(text, key).not.toMatch(/\.$/);
    }
  });
});
