// @vitest-environment jsdom
/**
 * DEF-BIL-10709 — the tester's L3-07: *"In the bill run, 'Late fee due' said
 * '1–20 of 20' but showed no rows until clicked again, and typing in 'Find
 * account' did not filter."*
 *
 * Three causes, one case each: the pager fell back to the CACHED tag count
 * while the page had not arrived; a failed read had no state at all; and every
 * keystroke and page re-ran the staleness sweep before answering.
 *
 * RED FIRST (law 7), against the tip: the pending case found "1–1 of 1" in the
 * pane, the failed case found no `[data-pane-failed]`, and the search case saw
 * no `sweep: 0` on any read.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RUN_ID } from "./__fixtures__/bulkRunFixtures";
import { mountRun } from "./__fixtures__/mountRun";

afterEach(cleanup);

const OPEN_RUN = `?run=${RUN_ID}`;

async function openPane(): Promise<HTMLElement> {
  fireEvent.click(await screen.findByRole("button", { name: /^Late fee due/ }, { timeout: 10000 }));
  return waitFor(() => {
    const pane = document.querySelector('[data-tag-pane="late_fee"]') as HTMLElement | null;
    expect(pane).not.toBeNull();
    return pane as HTMLElement;
  });
}

describe("DEF-BIL-10709 · the late-fee list's states and search", () => {
  it("while the page has not arrived it says Loading and shows no count", async () => {
    mountRun({ holdTagRead: "late_fee" }, OPEN_RUN);
    const pane = await openPane();
    expect(within(pane).getByText("Loading accounts…")).toBeInTheDocument();
    expect(pane.textContent ?? "").not.toMatch(/ of \d/);
  });

  it("a failed read says so and offers Try again — never an empty list", async () => {
    mountRun({ failTagRead: "late_fee" }, OPEN_RUN);
    const pane = await openPane();
    await waitFor(() => expect(pane.querySelector("[data-pane-failed]")).not.toBeNull());
    expect(within(pane).getByText("Accounts could not be loaded.")).toBeInTheDocument();
    expect(within(pane).getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(within(pane).queryByText("No accounts here.")).toBeNull();
  });

  it("only the first read sweeps; the search is sent once typing settles", async () => {
    const fake = mountRun({}, OPEN_RUN);
    const pane = await openPane();
    await waitFor(() => expect(pane.querySelector("[data-late-fee-total]")).not.toBeNull());
    const reads = () => fake.calls.filter((call) => call.query?.tag === "late_fee");
    expect(reads()[0]?.query?.sweep).toBeUndefined();

    fireEvent.change(within(pane).getByPlaceholderText("Find account"), { target: { value: "Xan" } });
    await waitFor(() => expect(reads().some((call) => call.query?.q === "Xan")).toBe(true), { timeout: 2000 });
    const searched = reads().filter((call) => call.query?.q !== "");
    // Debounced: one read for the settled term, not one per keystroke…
    expect(searched).toHaveLength(1);
    // …and it reads what is saved rather than sweeping again.
    expect(searched[0]?.query?.sweep).toBe(0);
  });
});
