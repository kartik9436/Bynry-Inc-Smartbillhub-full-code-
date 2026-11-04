// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  Record links (PO ruling 2026-10-19, decision log "Record links
//          (navigation design)") — every account number the bulk bill run
//          prints opens that account.
// Rules:   hard-won law 2 (a fixture that cannot tell a working link from a
//          broken one) — the page is mounted under its REAL route by
//          `mountRun`, so every address is asserted with its tenant.
// ───────────────────────────────────────────────────────
/**
 * Each account number the wizard prints is a NEW-TAB link to the account —
 * the shape the Check panes' Ready-to-bill cell already draws, so leaving the
 * wizard never loses the run. Asserted by the exact address, on the page as
 * a clerk reaches it.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CYCLE_ID, RUN_ID, accountNo } from "./__fixtures__/bulkRunFixtures";
import { TENANT, mountRun } from "./__fixtures__/mountRun";

afterEach(cleanup);

const OPEN_RUN = `?run=${RUN_ID}`;

function expectAccountLink(scope: HTMLElement, text: string, accountId: string) {
  const link = within(scope).getAllByRole("link", { name: text })[0];
  expect(link).toHaveAttribute("href", `/${TENANT}/accounts/${accountId}`);
  expect(link).toHaveAttribute("target", "_blank");
}

async function chooseCycle() {
  const select = await screen.findByLabelText(/^Cycle/);
  await waitFor(() => expect(within(select).getAllByRole("option").length).toBeGreaterThan(1));
  fireEvent.change(select, { target: { value: CYCLE_ID } });
}

describe("Record links · the bulk bill run's account numbers open the account", () => {
  it("Scope · Nobody to bill: the last account opens it", async () => {
    mountRun();
    await chooseCycle();
    fireEvent.click(await screen.findByRole("button", { name: "See units" }));
    const panel = screen.getByRole("dialog", { name: "Units" });
    await within(panel).findByText("1416 Elm St · Unit B");
    expectAccountLink(panel, "AC-2026-00099", "acc-99");
  });

  it("Scope · Missing meter: the unit's account opens it", async () => {
    mountRun();
    await chooseCycle();
    fireEvent.click(await screen.findByRole("button", { name: "See services" }));
    const panel = screen.getByRole("dialog", { name: "Services" });
    await within(panel).findByText("1408 Elm St · Unit A");
    expectAccountLink(panel, "AC-2026-00101", "acc-101");
  });

  it("Check · Pricing check: a differing bill's account opens it", async () => {
    mountRun({ pricing: "differ" }, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    const panel = await screen.findByRole("region", { name: "Pricing check" });
    await within(panel).findByText("3 bills differ");
    fireEvent.click(within(panel).getByRole("button", { name: "Show bills" }));
    expectAccountLink(panel, "AC-2026-00031", "acc-shadow-1");
  });

  it("Sign off · waived and credit-covered accounts open the account", async () => {
    mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    const waived = await waitFor(() => {
      const found = document.querySelector("[data-waived-list]") as HTMLElement;
      expect(found).not.toBeNull();
      return found;
    });
    expectAccountLink(waived, accountNo(10), "acc-10");
    const covers = await waitFor(() => {
      const found = document.querySelector('[data-run-table="credit-covers"]') as HTMLElement;
      expect(found).not.toBeNull();
      return found;
    });
    expectAccountLink(covers, "AC-2026-12910", "acc-30");
  });

  it("Sign off · Failed to draft: the account opens it", async () => {
    mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    fireEvent.click(await screen.findByRole("button", { name: "See breaks" }));
    const panel = screen.getByRole("dialog", { name: "Bills" });
    expectAccountLink(panel, "AC-2026-00902", "acc-20");
  });

  it("Sent · Not sent: the account opens it", async () => {
    mountRun({ phase: "issued", sendFailure: true }, OPEN_RUN);
    await screen.findByText("1,369 bills sent");
    const line = await screen.findByText("1 bill not sent.");
    fireEvent.click(within(line.parentElement as HTMLElement).getByRole("button", { name: "See breaks" }));
    const panel = await screen.findByRole("dialog", { name: "Sent" });
    expectAccountLink(panel, "AC-2026-00008", "acc-8");
  });

  it("Sent · Check report: the account opens it", async () => {
    mountRun({ phase: "issued" }, OPEN_RUN);
    await screen.findByText("1,369 bills sent");
    fireEvent.click(screen.getByRole("tab", { name: "Check report" }));
    const report = await waitFor(() => {
      const found = document.querySelector("[data-check-report]") as HTMLElement;
      expect(found).not.toBeNull();
      expect(found.querySelector('[data-run-table="check-report"]')).not.toBeNull();
      return found;
    });
    expectAccountLink(report, accountNo(5), "acc-5");
  });
});
