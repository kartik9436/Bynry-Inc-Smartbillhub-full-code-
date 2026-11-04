// ── Trace ──────────────────────────────────────────────
// Change:   `CR-137-BRC07` `P3.11` — the sixth payment status, `cancelled`.
// Defects:  hard-won law 2 (*"built is not wired … it fails SILENTLY"*) and its
//           named precedent — the ELEVENTH utility service that never appeared
//           on the sign-up screen, which is why `SignupWizard.test.tsx` asserts
//           a COUNT. This file is that test, for payment statuses.
// Rules:    B14 rule 31 (nothing internal is ever visible to a utility user) ·
//           rule 35 (a catalogue is written in its own language) · G15 (every
//           catalogue holds the same key set)
// ───────────────────────────────────────────────────────
// THE TEST THAT FAILS THE DAY A SEVENTH STATUS IS ADDED AND NOT TYPED IN.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ WHY A COUNT AND NOT A LOOP OVER THE LIST
// ══════════════════════════════════════════════════════════════════════════
// A test that walks `PAYMENT_STATUSES` and checks each one has a word is green
// on a list with one entry. **The failure this file exists for is a list that
// is too SHORT**, and only an asserted COUNT can see that — which is exactly
// the reasoning behind `SignupWizard.test.tsx` asserting eleven services, and
// `CLAUDE.md` records that test existing because the same thing happened once
// already with an eleventh service that the sign-up screen never offered.
//
// **The number below is therefore load-bearing and must be changed BY HAND**,
// in the same commit as the status, by somebody who has also added the word to
// eleven catalogues. That deliberate friction is the whole mechanism.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ WHAT THE ABSENCE ACTUALLY LOOKED LIKE, BECAUSE IT WAS NOT SILENCE
// ══════════════════════════════════════════════════════════════════════════
// `paymentStatusLabel` resolves `payments.status.${status}`, and i18next returns
// the KEY when it misses. So between `payments/0036` landing and this commit, a
// cancelled payment's status pill would have rendered the literal string
// **`payments.status.cancelled`** — an internal reference on a clerk's screen,
// which B14 rule 31 forbids by name. `tsc` passed. Every suite passed. Nothing
// had cancelled a payment yet, so nothing could see it.
//
// RED FIRST (hard-won law 7): each case below was shown failing against the
// pre-fix tree — the count case at five, and the catalogue case on the missing
// `payments.status.cancelled` key — before it was trusted green.
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { PAYMENT_STATUSES } from "@/api/endpoints";

import { PAYMENT_STATUS_FILTER_ORDER, paymentStatusLabel, paymentStatusTone } from "./paymentsShared";

/**
 * `apps.payments.models.PAYMENT_STATUSES` — SIX since `payments/0036`
 * (`CR-137-BRC07` `P3.5`, 2026-09-23).
 *
 * ⚠ **CHANGING THIS NUMBER IS THE POINT.** If you are here because this test is
 * red, the server has a status the front end does not: add it to
 * `PAYMENT_STATUSES` in `api/endpoints.ts`, give it a tone in
 * `paymentStatusTone`, write its word into all eleven catalogues through
 * `10-scripts/i18n_fanin.py`, and then move this number.
 */
const STATUSES_ON_THE_SERVER = 6;

describe("the payment status list matches the server's, and every status has a word", () => {
  it(`carries all ${STATUSES_ON_THE_SERVER} statuses — a short list is the defect`, () => {
    expect(PAYMENT_STATUSES).toHaveLength(STATUSES_ON_THE_SERVER);
  });

  it("names cancelled, the one phase 3 added", () => {
    // Named explicitly as well as counted: a count alone would stay green if
    // somebody swapped one status for another.
    expect(PAYMENT_STATUSES).toContain("cancelled");
  });

  it("every status resolves to a WORD and never to its own key", () => {
    for (const status of PAYMENT_STATUSES) {
      const label = paymentStatusLabel(status, (key, params) => i18n.t(key, params));
      // ⚠ **THE ASSERTION THAT MATTERS IS *NOT THE KEY*.** i18next returns the
      // key on a miss, so `expect(label).toBeTruthy()` is green on a missing
      // word — a check that cannot fail (hard-won law 7's second shape).
      expect(label).not.toBe(`payments.status.${status}`);
      expect(label).not.toContain("payments.status.");
      expect(label.trim()).not.toBe("");
    }
  });

  it("B14 rule 31: no status word carries an internal reference", () => {
    for (const status of PAYMENT_STATUSES) {
      const label = paymentStatusLabel(status, (key, params) => i18n.t(key, params));
      expect(label).not.toMatch(/\b(BR-|US-|DEF-|OQ-|payments\.)/);
    }
  });

  it("every status has a tone, and money that did not stay reads as danger", () => {
    for (const status of PAYMENT_STATUSES) {
      expect(["success", "warning", "danger", "neutral", "info"]).toContain(
        paymentStatusTone(status),
      );
    }
    // The three that mean *the money is not there*. `cancelled` joining them is
    // a decision (see `paymentStatusTone`'s own note), not a fall-through
    // nobody looked at.
    expect(paymentStatusTone("failed")).toBe("danger");
    expect(paymentStatusTone("reversed")).toBe("danger");
    expect(paymentStatusTone("cancelled")).toBe("danger");
    // And the control: a status that DID stay must not read as danger, or the
    // assertion above would pass on a function that returned "danger" always.
    expect(paymentStatusTone("cleared")).toBe("success");
    // CR-186-BRC10: `posted` is where every new payment starts and its money
    // counts from that moment, so it reads as money that stayed too.
    expect(paymentStatusTone("posted")).toBe("success");
  });

  it("CR-186-BRC10: the Status filter offers all six, posted then cleared first", () => {
    // The list read five until 2026-10-21 and had never offered `cancelled`.
    expect([...PAYMENT_STATUS_FILTER_ORDER].sort()).toEqual([...PAYMENT_STATUSES].sort());
    expect(PAYMENT_STATUS_FILTER_ORDER.slice(0, 2)).toEqual(["posted", "cleared"]);
  });
});
