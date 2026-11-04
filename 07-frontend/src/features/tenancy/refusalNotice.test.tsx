// ── Trace ──────────────────────────────────────────────
// Component: RefusalNotice + ArrivesWith (features/tenancy/settingsShared.tsx)
// Defects:   DEF-332 (the server's br_ref printed to a utility clerk) ·
//            DEF-445 / DEF-421 (a stated absence that cites nothing outlives
//            its reason and nothing notices)
// Rules:     B8 (br_ref is MANDATORY on every BIZ refusal) · BR-SHL-020 r2 ·
//            PO ruling 2026-08-19 — "all these messages should not be on
//            screen for user"
// ───────────────────────────────────────────────────────
//
// TWO PROPERTIES, AND THEY PULL AGAINST EACH OTHER — which is exactly why they
// are asserted together in one file. DEF-332 sat open for two days because two
// PO rulings nine days apart pointed opposite ways: 2026-08-10 asked for a
// support-grade identifier after the PO could not see what had failed, and
// 2026-08-19 refused BR-codes on a utility's screen. The resolution is not
// "drop the id" and it is not "keep the id" — it is that the id LEAVES THE
// SENTENCE AND STAYS IN THE DOM. A test that asserted only the first half would
// pass on a product that had thrown the id away, which is the half B8 forbids.
//
// RED PROVED FIRST (hard-won law 7), both directions:
//   · with the `<span className="settings-refusal-ref"> ({brRef})</span>` put
//     back, `not.toContain("BR-IDN-013")` fails on the rendered text;
//   · with `data-br-ref` removed from the strip, the second assertion fails and
//     the first still passes — the failure a one-sided test cannot see.

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ArrivesWith, RefusalNotice } from "./settingsShared";

/**
 * The string the PO was shown on 2026-08-19, minus its id.
 *
 * ⚠ The real copy reads *"You can't deactivate this one."* and the apostrophe is
 * dropped HERE only: `renderToStaticMarkup` escapes it to `&#x27;`, so a literal
 * `toContain` on the real sentence fails for a reason that has nothing to do
 * with the rule under test. Asserting the escaped form instead would pin an
 * encoding, not a message.
 */
const SENTENCE = "A utility needs one active System Admin. Deactivate a different one.";

describe("RefusalNotice — DEF-332", () => {
  it("renders the sentence and NOT the rule id a clerk cannot use", () => {
    const html = renderToStaticMarkup(
      <RefusalNotice refusal={{ message: SENTENCE, brRef: "BR-IDN-013" }} />,
    );
    expect(html).toContain(SENTENCE);
    // The whole of the 2026-08-19 ruling, as one assertion.
    expect(html).not.toContain("(BR-IDN-013)");
  });

  it("still CARRIES the rule id, on data-br-ref, because B8 makes it mandatory", () => {
    const html = renderToStaticMarkup(
      <RefusalNotice refusal={{ message: SENTENCE, brRef: "BR-IDN-013" }} />,
    );
    // ⚠ This is the assertion that stops the fix becoming a deletion. Support
    // and the audit trail both read this value; the browser inspector and a
    // Playwright locator both reach it here. A console line would not survive a
    // re-render, a screenshot, or an accessibility tree.
    expect(html).toContain('data-br-ref="BR-IDN-013"');
  });

  it("writes no attribute at all when the server cited no rule", () => {
    // A system error is not a rule refusal and carries no br_ref. An empty
    // `data-br-ref=""` would read as "a rule with no name" to whoever greps it.
    const html = renderToStaticMarkup(
      <RefusalNotice refusal={{ message: "Something went wrong.", brRef: null }} />,
    );
    expect(html).not.toContain("data-br-ref");
  });
});

describe("ArrivesWith — DEF-445, a stated absence carries its expiry", () => {
  it("puts `tracks` on data-tracks and never in the sentence", () => {
    const message = "The classes are set up and this plan can store the amounts.";
    const html = renderToStaticMarkup(
      <ArrivesWith title="Deposits" message={message} tracks="DEF-445" />,
    );
    expect(html).toContain(message);
    expect(html).toContain('data-tracks="DEF-445"');
    // ⚠ THE FIRST FIX OF DEF-445 PUT THE ID INSIDE THE COPY — "(DEF-445)" — on
    // a screen a billing clerk at a two-person utility reads. That is DEF-332's
    // shape arriving through the door of another defect's fix, and this line is
    // what refuses it.
    expect(html).not.toContain("(DEF-445)");
  });

  it("renders no attribute when nothing is cited, so G38 can count it", () => {
    const html = renderToStaticMarkup(<ArrivesWith title="Reads" message="Not built yet." />);
    expect(html).not.toContain("data-tracks");
  });
});
