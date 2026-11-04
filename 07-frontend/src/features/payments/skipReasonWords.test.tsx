// ── Trace ──────────────────────────────────────────────
// Rules:  B14 rule 31 — no internal code is ever the visible value of a field.
// Defect: DEF-PAY-6284 — two of the three codes `notices.py` emits had no
//         catalogue entry, so the Send-notice wizard's last step printed
//         `payments.skip.tier_already_sent` to a clerk.
// Tests:  the CODE side is owned by
//         06-backend/tests/test_def_pay_6284_skip_codes_have_words.py, which
//         walks the emitters. This file owns the RENDERER's fallback.
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY A FALLBACK TEST AT ALL, WHEN THE BACKEND TEST MAKES IT UNREACHABLE.**
// `SkipCell` has promised this behaviour in its own docstring since it shipped
// — *"an unknown code renders the fact of the skip without pretending to know
// why"* — and did not do it. Hard-won law 1: a comment claiming a guarantee is
// not the guarantee. The guarantee is now code, so it gets a test; without one
// it is a comment again the first time somebody "simplifies" the two lines
// back to `t(key)`.
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ladderSkipLabel } from "@/features/payments/paymentsShared";

const t = ((key: string, params?: Record<string, unknown>) =>
  i18n.t(key, params)) as Parameters<typeof ladderSkipLabel>[1];

describe("DEF-PAY-6284 — a skip reason reaches a clerk as words", () => {
  it("renders the real wording for a code the catalogue knows", () => {
    expect(ladderSkipLabel("tier_already_sent", t)).toBe("This step already went out");
    expect(ladderSkipLabel("collections_paused_by_active_plan", t)).toBe(
      "Paused by an active payment plan",
    );
    expect(ladderSkipLabel("medical_hold", t)).toContain("Medical hold");
  });

  it("never returns the raw key, for any code the backend can emit", () => {
    // The ten live codes across `ladder.py` and `notices.py`. Listed here as a
    // mirror; the backend test is what keeps the list honest against the code.
    const codes = [
      "below_ladder_floor",
      "medical_hold",
      "payment_plan_pause",
      "partial_payment_pause",
      "nothing_overdue",
      "next_step_not_due",
      "ladder_complete",
      "already_noticed_today",
      "tier_already_sent",
      "collections_paused_by_active_plan",
    ];
    for (const code of codes) {
      const label = ladderSkipLabel(code, t);
      expect(label).not.toBe(`payments.skip.${code}`);
      expect(label).not.toContain("payments.skip.");
    }
  });

  it("states the FACT of a skip for a code nothing has catalogued yet", () => {
    // This is the case that was broken: an uncatalogued code fell through as
    // its own key. It now says a clerk-readable sentence instead.
    const label = ladderSkipLabel("a_code_invented_after_this_test", t);
    expect(label).toBe("Skipped for an unlisted reason");
    expect(label).not.toContain("payments.skip.");
    expect(label).not.toContain("a_code_invented_after_this_test");
  });
});
