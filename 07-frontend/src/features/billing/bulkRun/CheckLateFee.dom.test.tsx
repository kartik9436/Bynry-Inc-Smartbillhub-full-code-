// @vitest-environment jsdom
/**
 * DEF-BIL-10200 — the bill run's late fee on the Check (decision log
 * 2026-10-17, *"THE LATE FEE IS APPLIED BY THE BILL RUN"*).
 *
 * The *Late fee due* pane says how many accounts and how much in all
 * (*"1 account · late fees $5.00"*), each row its own figure, each row
 * answered *Apply* until a clerk waives it — and Waive is offered per
 * account only, never for the whole tag (BR-BIL-003).
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RUN_ID } from "./__fixtures__/bulkRunFixtures";
import { mountRun } from "./__fixtures__/mountRun";

afterEach(cleanup);

const OPEN_RUN = `?run=${RUN_ID}`;

async function openLateFees(): Promise<HTMLElement> {
  fireEvent.click(await screen.findByRole("button", { name: /^Late fee due/ }));
  return waitFor(() => {
    const pane = document.querySelector('[data-tag-pane="late_fee"]') as HTMLElement | null;
    expect(pane?.querySelector("[data-late-fee-total]")).not.toBeNull();
    return pane as HTMLElement;
  });
}

describe("DEF-BIL-10200 · late fees on the Check", () => {
  it("states the count and the total, and each row's figure", async () => {
    mountRun({}, OPEN_RUN);
    const pane = await openLateFees();
    expect(within(pane).getByText("1 account · late fees $5.00")).toBeInTheDocument();
    expect(within(pane).getByText("$5.00 on $100.00 overdue.")).toBeInTheDocument();
  });

  it("DEF-BIL-10202: no Needs-a-decision pill, no fix-screen sentence, one count line", async () => {
    mountRun({}, OPEN_RUN);
    const pane = await openLateFees();
    expect(within(pane).queryByText("Needs a decision")).toBeNull();
    expect(pane.textContent ?? "").not.toMatch(/Fixed in Payments/);
    expect(pane.querySelector("[data-pane-line]")).toBeNull();
    // No bulk answer exists on this tag, so a row checkbox would select for nothing.
    expect(within(pane).queryAllByRole("checkbox")).toHaveLength(0);
  });

  it("each row reads Apply until waived, and Waive is per account only", async () => {
    const fake = mountRun({}, OPEN_RUN);
    const pane = await openLateFees();
    expect(within(pane).getByText("Waive one account at a time.")).toBeInTheDocument();
    expect(within(pane).queryByRole("radio", { name: "Waive" })).toBeNull();
    expect(pane.querySelector("[data-apply-all]")).toBeNull();
    const row = pane.querySelector("#decide-acc-9-all") as HTMLSelectElement;
    expect(row.value).toBe("apply");
    fireEvent.change(row, { target: { value: "waive" } });
    await waitFor(() => {
      const post = fake.calls.filter((call) => call.path.endsWith("/check/decisions")).at(-1);
      expect(post?.body).toEqual({ case: "late_fee", choice: "waive", scope: "accounts", account_ids: ["acc-9"] });
    });
  });
});
