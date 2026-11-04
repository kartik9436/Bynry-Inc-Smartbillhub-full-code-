// ── Trace ──────────────────────────────────────────────
// Defects: DEF-RAT-8703 (the toast said "is live" over a list row that said
//          Draft and Change scheduled) · DEF-RAT-8704 (Fix an error hides the
//          dates by rule and never said how to move them) · DEF-RAT-8705 (the
//          screen half: a filed-ahead version is drawn as "no bills", which the
//          server now answers with 0 instead of null).
//          The PO's beta report of 2026-10-01, v2.418.9, ottumwa-water-works.
// Rules:   BR-RAT-104 / BR-RAT-1016 verb 2 (a correction keeps the window) ·
//          US-RAT-004 §5 (the status is DERIVED by the server) · B14 rule 33
//          (an instruction is at most six words a sentence; rationale is zero).
// Tests:   the browser half is 10-scripts/def_rat_filed_ahead_correction_walk.mjs
// ───────────────────────────────────────────────────────
/**
 * ⚠ **PROVED RED FIRST (hard-won law 7).** With `1129ec6b4`'s wizard in place,
 * 5 of these 9 cases fail (`commitToast` does not exist and `EffectiveStep` is
 * not exported, so neither the toast nor the hint can be asked about), and the
 * walk script's `EXPECT=before` run recorded the three symptoms in a browser
 * (`before-*.png`). The four that pass there are catalogue and copy checks.
 *
 * ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a toast picked from the MODE alone
 * passes every case that saves an active schedule, so the cases below hand it
 * a `draft` status with a scheduled date — the exact answer the server gave the
 * PO — and assert the sentence names the date and does not say live.
 */
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

// `DEF-GOV-10106` — the DEF-RAT-8704/8705 cases rendered the old five-step
// wizard's `EffectiveStep` and `IssuedBillsNote`, which left with that wizard
// (the three-step one replaced it on 2026-10-01, `5804b0fc1`; retirement filed
// as `DEF-RAT-8755`). The toast the three-step wizard still uses stays pinned.
import { commitToast } from "./RateScheduleWizard";

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

describe("DEF-RAT-8703 — the toast says what the saved schedule says", () => {
  it("a version that starts tomorrow names its start date and does not say live", () => {
    const toast = commitToast("activate", { status: "draft", scheduled_change: "2026-10-01" });
    expect(toast).toEqual({ key: "rating.rate.toast.scheduled", date: "2026-10-01" });
    const sentence = t(toast.key, { name: "Res Water", date: "10/01/2026" });
    expect(sentence).toContain("Res Water");
    expect(sentence).toContain("10/01/2026");
    expect(sentence).not.toContain(t("rating.rate.toast.activated", { name: "" }).trim());
    expect(sentence).not.toMatch(/live/i);
  });

  it("a schedule in force today is still live", () => {
    expect(commitToast("activate", { status: "active", scheduled_change: "2027-01-01" }).key).toBe(
      "rating.rate.toast.activated",
    );
  });

  it("a draft save is still a draft save", () => {
    expect(commitToast("draft", { status: "draft", scheduled_change: null }).key).toBe(
      "rating.rate.toast.draft",
    );
  });

  it("nothing in force and nothing scheduled never claims either", () => {
    const toast = commitToast("activate", { status: "draft", scheduled_change: null });
    expect(toast.key).toBe("rating.rate.toast.saved");
    expect(t(toast.key, { name: "Res Water" })).not.toMatch(/live/i);
  });

  it("every new sentence is in the catalogue", () => {
    for (const key of [
      "rating.rate.toast.scheduled",
      "rating.rate.toast.saved",
      "rating.rate.correct.datesHint",
    ]) {
      expect(t(key, { name: "N", date: "D" })).not.toBe(key);
    }
  });
});
