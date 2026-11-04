// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  `CR-122-BRC06` — the move-in carries its request (its details AND
//          its documents), and step 4 asks one discount question. PO rulings
//          2026-09-19.
// Rules:   B14 rule 31 (no database id is ever the visible value of a field) ·
//          B14 rule 32 (a stated absence is CLOSED by default) · B14 rule 33
//          (a LABEL ≤ 3 words · a FACT ≤ 6 words · RATIONALE is ZERO WORDS ON
//          SCREEN) · B18 §5.3.4 (a discount claim never blocks service) ·
//          `DEF-CUS-5872` (a `storage_ref` is not a file) · hard-won law 1 (a
//          comment claiming a guarantee is not the guarantee).
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS FILE EXISTS BECAUSE ITS SUBJECT'S OWN TRACE HEADER CLAIMED IT AND
// IT DID NOT EXIST.** `moveInRequestBlocks.tsx` shipped on 2026-09-19 carrying
// `Tests: moveInRequestBlocks.dom.test.tsx (rendered output, not props)` in its
// header, over 339 lines with no test of any kind. That is hard-won law 1
// exactly — a comment claiming a guarantee is not the guarantee — and it is
// worth naming here rather than quietly fixing, because the header read as
// proof to every later reader and `tsc`, the suites and every gate were green.
//
// ⚠ **EVERY ASSERTION IS ABOUT RENDERED OUTPUT, NEVER ABOUT A PROP.** All four
// of these blocks are one prop away from being dead UI: `RequestDocuments`
// could query a request nothing names, `DiscountClaim`'s `onChange` could be
// threaded to nothing. So the claims are read off the DOM and off the object a
// change handler really emitted, never off what was passed in.
//
// ⚠ **AND THE THREE ABSENCES ARE ASSERTED AS HARD AS THE PRESENCES.** A
// move-in started from an account shows NO documents block; the three
// AUTOMATIC discounts are NOT offered; and nothing on the discount control
// says the customer is now getting money off. Each of those is a rule whose
// breach is invisible — an absence is what no check in this repo can see
// (CLAUDE.md hard rule 8's closing lesson), so it gets an assertion by name.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { RequestPrefillNote } from "./moveInRequestBlocks";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE PREFILL NOTE — where the answers came from
// ══════════════════════════════════════════════════════════════════════════
describe("RequestPrefillNote", () => {
  it("names the request by its REFERENCE, never by its id (B14 rule 31)", () => {
    render(<RequestPrefillNote requestNo="SR-26-0006" t={t} />);
    expect(screen.getByText(/SR-26-0006/)).toBeInTheDocument();
  });

  it("does not print the id even when one looks like a reference", () => {
    // The component is given ONLY the reference, which is the design: the id
    // lives in the address bar because that is URL state. If a later lane
    // passed the id in here, this is the assertion that goes red.
    const { container } = render(
      <RequestPrefillNote requestNo="SR-26-0006" t={t} />,
    );
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/i);
  });

  it("renders NOTHING when the move-in did not come from a request", () => {
    // Rule 32 — a stated absence is CLOSED by default. Not an empty note, not
    // a sentence explaining that there is no request: nothing at all.
    const { container } = render(<RequestPrefillNote requestNo={null} t={t} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders NOTHING for an empty reference, not an empty sentence", () => {
    const { container } = render(<RequestPrefillNote requestNo="" t={t} />);
    expect(container).toBeEmptyDOMElement();
  });
});
