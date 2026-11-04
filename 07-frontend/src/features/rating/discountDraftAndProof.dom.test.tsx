// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-RAT-5817 — a discount could be edited exactly ONCE, and the
//          draft doing the blocking was visible nowhere in the product ·
//          DEF-RAT-5816 — *Apply and approve, with proof* with no document
//          ticked was refused at the COMMIT by the literal string
//          `rating.discounts.proof_kinds_required`, printed raw on screen.
// Rules:   BR-RAT-031 (one draft at a time) · BR-RAT-037 (append-only) ·
//          BR-RAT-076 (a programme demanding proof names its documents) ·
//          B14 rule 31 (no database id on screen) · B14 rule 32 (no internal
//          code in clerk-facing copy) · B14 rule 33 (the copy caps) ·
//          CLAUDE.md hard-won law 2 (built is not wired) · law 7
// Screens: DIS-02 step 3 · DIS-03 `?tab=audit`
// ───────────────────────────────────────────────────────
/**
 * **THE TWO THINGS A CLERK COULD NOT DO, AND THE ONE THING THEY SHOULD NOT SEE.**
 *
 * ── PROVED RED FIRST (hard-won law 7), through `vitest`, the harness that runs
 * ── them. What each printed before the change ──────────────────────────────
 *
 * * `the key the server raises has a sentence in every catalogue` —
 *
 *       AssertionError: expected undefined to be a string
 *         (en.json held no `rating.discounts.proof_kinds_required`, which is
 *          why the clerk read the key itself)
 *
 * * `step 3 blocks Continue when proof is demanded and nothing is ticked` —
 *
 *       SyntaxError: The requested module './DiscountWizard' does not provide
 *       an export named 'proofWithNoAcceptedDocuments'
 *
 * * `the objection is drawn at the control, not five screens later` —
 *
 *       AssertionError: expected '// ── Trace ──…' to contain
 *       'proofWithNoAcceptedDocuments(draft)'
 *
 * * `the audit tab lists the draft and offers the only way to discard it` —
 *
 *       Error: Failed to resolve import "./discountDetailTabs"
 *
 * ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, asked before they were written.**
 * A test that only asserted *the discard button renders* would pass over a
 * button wired to nothing — hard-won law 2's dead control, which cost this
 * repo eight doors on one portal page. So the click is followed through to the
 * confirm dialog and then to the CLIENT CALL, and the id it carries is
 * asserted to be the DRAFT's rather than the active version's. Discarding the
 * wrong row would be a silent money-path defect wearing a passing test.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";

// ══════════════════════════════════════════════════════════════════════════
// DEF-RAT-5816 — the refusal a clerk could not read, and where it now lands
// ══════════════════════════════════════════════════════════════════════════

// ⚠ **`DiscountWizard.tsx` IS RETIRED (CR-166-BRC10 round 3 task 7).** The New
// door opens `discountForm/NewDiscountWizard.tsx` and the Edit door
// `discountForm/EditDiscountForm.tsx`; the cases that read the old wizard's
// source or its exports went with it. The server derives a proof condition's
// accepted documents from *Who qualifies* (decision log, 2026-10-03), so the
// form has no documents box left to block on.
describe("DEF-RAT-5816 · proof demanded with no document named", () => {
  it("the key the server raises now has a sentence — the clerk read the KEY", () => {
    // `_validate_version`'s GATE 2 raises this exact string. It was in
    // `core/refusal_keys_parked.txt` and in none of the eleven catalogues, so
    // i18next rendered the key itself: `rating.discounts.proof_kinds_required`
    // on screen, which is also B14 rule 32 (no internal code in clerk copy).
    const sentence = (en as Record<string, string>)["rating.discounts.proof_kinds_required"];
    expect(typeof sentence).toBe("string");
    expect(sentence).not.toContain("rating.");
    // B14 rule 33 — an instruction is capped at six words per sentence.
    for (const part of sentence.split(/(?<=[.?!])\s+/).filter(Boolean)) {
      expect(part.trim().split(/\s+/).length).toBeLessThanOrEqual(6);
    }
  });

});

// ══════════════════════════════════════════════════════════════════════════
// DEF-RAT-5817 — the blocking draft, now visible and withdrawable
// ══════════════════════════════════════════════════════════════════════════

// ⚠ DEF-RAT-5817's Audit-tab discard cases were RETIRED by CR-166-BRC10 round 3
// task 6 (2026-10-03) together with `discountDetailTabs.tsx`: the versions are
// a table on Overview and the discard is *Delete draft* in the header's More ▾
// — asserted, with the draft's own id on the wire, in
// `discountDetail/discountDetail.dom.test.tsx`.
