// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-6423 — after a waive the request's fee panel read
//          "Application fee $0.00 waived. BILLERR": the collected-side figure
//          where the WAIVED one belongs, and the reason's CODE where the
//          utility's own name for it belongs (B14 rules 31/32).
// ───────────────────────────────────────────────────────
/**
 * The panel is driven with the payload `fees_tab` now serves after a clerk
 * waives a $45.00 fee for `BILLERR`: `quoted` is 0.00 (it sums the UNWAIVED
 * lines), `waived` is 45.00, and the line carries both the stored code and
 * the name Settings gives it.
 *
 * ⚠ WHAT WOULD MAKE THIS PASS WRONGLY: asserting only that "waived" appears.
 * The broken panel said "waived" too. So the amount, the name and the absence
 * of the code are each asserted on the one rendered sentence.
 */
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApplicationFeeLine } from "./serviceRequestShared";

afterEach(cleanup);

const usd = (amount: string, display: string) => ({ amount, display, currency: "USD" });

describe("DEF-CUS-6423 · a waived application fee reads its amount and its reason's name", () => {
  it("waive 45.00 with BILLERR → '45.00 waived' and 'Billing error correction', never the code", () => {
    render(
      <ApplicationFeeLine
        t={i18n.t.bind(i18n)}
        fees={{
          quoted: usd("0.0000", "0.00"),
          waived: usd("45.0000", "45.00"),
          collected: usd("0.0000", "0.00"),
          receipt_no: null,
          lines: [
            { waived: true, waive_reason_name: "Billing error correction" },
          ],
        }}
      />,
    );
    const line = screen.getByText(/waived/);
    expect(line).toHaveAttribute("data-fee-line", "waived");
    expect(line.textContent).toContain("45.00 waived");
    expect(line.textContent).not.toContain("0.00 waived. ");
    expect(line.textContent).toContain("Billing error correction");
    expect(line.textContent).not.toContain("BILLERR");
  });
});
