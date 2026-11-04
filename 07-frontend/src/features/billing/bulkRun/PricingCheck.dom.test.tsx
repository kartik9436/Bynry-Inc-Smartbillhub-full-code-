// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Ruling:  OQ-BIL-12791 → A (PO 2026-10-13, decision log "THREE PO RULINGS ON
//          THE LEFT-OVER SCREEN PIECES") — the bulk run's Check step shows the
//          pricing check again
// Defect:  DEF-BIL-10121 — the comparison was lost from the run in 91eca0bff
// Rules:   B14 rule 33 (a fact ≤ 6 words), law 2 (built is not wired)
// ───────────────────────────────────────────────────────
/**
 * The pricing check on the bulk bill run's Check step, mounted under the REAL
 * route pattern through the whole page — so a Check step that stops drawing it
 * goes red here, which is the test `91eca0bff` did not have.
 *
 * ⚠ **LOADING AND FAILED NEVER READ AS 0.** "0 differences" is what most months
 * look like, so a read in flight, a read that failed and a body the screen
 * cannot read must each say what they are and never print that sentence.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RUN_ID } from "./__fixtures__/bulkRunFixtures";
import { mountRun } from "./__fixtures__/mountRun";

afterEach(cleanup);

const OPEN_RUN = `?run=${RUN_ID}`;
const SHADOW = `/billing/runs/${RUN_ID}/pricing-shadow`;

async function pricingCheck() {
  await screen.findByText(/Checked 1,406 accounts at/);
  return screen.findByRole("region", { name: "Pricing check" });
}

describe("DEF-BIL-10121 · the pricing check on the bulk run's Check step (OQ-BIL-12791 → A)", () => {
  it("a month with no differences reads 0 differences, from the served comparison", async () => {
    const fake = mountRun({}, OPEN_RUN);
    const panel = await pricingCheck();
    await within(panel).findByText("0 differences");
    expect(within(panel).queryByRole("button", { name: "Show bills" })).toBeNull();
    expect(fake.calls.some((call) => call.method === "GET" && call.path === SHADOW)).toBe(true);
  });

  it("differences read as a count, and the differing bills list with both figures and no subtraction", async () => {
    mountRun({ pricing: "differ" }, OPEN_RUN);
    const panel = await pricingCheck();
    await within(panel).findByText("3 bills differ");
    expect(within(panel).queryByText("AC-2026-00031")).toBeNull();
    fireEvent.click(within(panel).getByRole("button", { name: "Show bills" }));
    for (const account of ["AC-2026-00031", "AC-2026-00047", "AC-2026-00112"]) {
      expect(within(panel).getAllByText(account).length).toBeGreaterThan(0);
    }
    // An account the two paths agreed on is counted, never listed.
    expect(within(panel).queryByText("AC-2026-00001")).toBeNull();
    expect(panel).toHaveTextContent("18.50");
    expect(panel).toHaveTextContent("22.70");
    // 22.70 − 18.50 = 4.20: nothing on this screen subtracts the two figures.
    expect(panel).not.toHaveTextContent("4.20");
    fireEvent.click(within(panel).getByRole("button", { name: "Hide bills" }));
    expect(within(panel).queryByText("AC-2026-00047")).toBeNull();
  });

  it("a failed read says so, never 0 differences, and Try again asks again", async () => {
    const fake = mountRun({ pricing: "failed" }, OPEN_RUN);
    const panel = await pricingCheck();
    await within(panel).findByText("Pricing check did not load.");
    expect(panel).not.toHaveTextContent("0 differences");
    const before = fake.calls.filter((call) => call.path === SHADOW).length;
    fireEvent.click(within(panel).getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(fake.calls.filter((call) => call.path === SHADOW).length).toBe(before + 1));
  });

  it("a one-off run with no billing cycle draws no pricing line, never a false 'did not load'", async () => {
    const fake = mountRun({ pricing: "no_cycle" }, OPEN_RUN);
    await waitFor(() => expect(fake.calls.some((call) => call.path === SHADOW)).toBe(true));
    await waitFor(() => expect(document.querySelector("[data-pricing-check]")).toBeNull());
    expect(screen.queryByText("Pricing check did not load.")).toBeNull();
  });

  it("a body the screen cannot read is a failed read, never a row of zeros", async () => {
    mountRun({ pricing: "unreadable" }, OPEN_RUN);
    const panel = await pricingCheck();
    await within(panel).findByText("Pricing check did not load.");
    expect(panel).not.toHaveTextContent("0 differences");
  });

  it("while the comparison is still being worked out it says so, never 0 differences", async () => {
    mountRun({ pricing: "hold" }, OPEN_RUN);
    const panel = await pricingCheck();
    expect(within(panel).getByText("Checking pricing…")).toBeInTheDocument();
    expect(panel).not.toHaveTextContent("0 differences");
  });

  it("nothing worked out twice reads No bills checked, never 0 differences", async () => {
    mountRun({ pricing: "nothing" }, OPEN_RUN);
    const panel = await pricingCheck();
    await within(panel).findByText("No bills checked");
    expect(panel).not.toHaveTextContent("0 differences");
  });
});
