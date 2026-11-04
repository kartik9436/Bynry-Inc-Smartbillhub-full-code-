// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Screen:   S31 · BIL-02 — the bulk bill run
// Defects:  DEF-BIL-9004 · DEF-BIL-9005 · DEF-BIL-9006 · DEF-BIL-9008 ·
//           DEF-BIL-9010 — found on the 40,015-account close-out walk,
//           2026-10-01 (04-docs/05-modules/07-billing/21-bulk-run-po-walkthrough.md)
// Tracker:  BULK-CHG-39 (Calculating between step 2 and 3)
// ───────────────────────────────────────────────────────
/**
 * THE CLOSE-OUT WALK'S SCREEN DEFECTS, EACH WRITTEN RED FIRST ON 2.437.5.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RUN_ID } from "./__fixtures__/bulkRunFixtures";
import { mountRun } from "./__fixtures__/mountRun";
import { stepForRun } from "./BulkRunPage";

afterEach(cleanup);

const OPEN_RUN = `?run=${RUN_ID}`;

async function openTagPane(name: string, code: string): Promise<HTMLElement> {
  fireEvent.click(await screen.findByRole("button", { name: new RegExp(`^${name}`) }));
  return waitFor(() => {
    const found = document.querySelector<HTMLElement>(`[data-tag-pane="${code}"]`);
    expect(found).not.toBeNull();
    return found as HTMLElement;
  });
}

describe("DEF-BIL-9010 · a run re-opened mid-Calculate shows the progress, not Sign off", () => {
  it("a live Calculate keeps the run on Check, whatever drafts exist", () => {
    expect(stepForRun({ phase: "calculated", calculating: { status: "running" } })).toEqual({ step: 2, sent: false });
    expect(stepForRun({ phase: "calculated", calculating: { status: "queued" } })).toEqual({ step: 2, sent: false });
    expect(stepForRun({ phase: "calculated", calculating: null })).toEqual({ step: 3, sent: false });
    // DEF-BIL-9004 — Check again on a run that already holds drafts.
    expect(stepForRun({ phase: "calculated", checking: { status: "running" } })).toEqual({ step: 2, sent: false });
  });

  it("opens on the Calculating panel, titled for its first pass with its n of N, then Sign off once it ends", async () => {
    mountRun({ phase: "calculated", calculatingLive: true }, OPEN_RUN);
    const panel = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-run-progress="calculating"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(panel).toHaveTextContent("Reading accounts");
    expect(panel).toHaveTextContent(/3,000 of 40,009/i);
    expect(screen.queryByText("Run summary")).toBeNull();
    await screen.findByText("Run summary", undefined, { timeout: 5000 });
  });
});

describe("DEF-BIL-9004 · Check again takes Price away at once, before the Check read answers", () => {
  it("the old results and their Price button go the moment the Check is accepted", async () => {
    // At 40,015 accounts `GET …/check` takes ~2 s; on 2.438.4 the old results
    // and a pressable Price stayed up for that long after Check again.
    mountRun({ holdCheckReadAfterStart: true }, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    expect(screen.getByRole("button", { name: /^Price/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));
    await waitFor(() => expect(document.querySelector('[data-run-progress="checking"]')).not.toBeNull());
    expect(screen.queryByRole("button", { name: /^Price/ })).toBeNull();
  });
});

describe("DEF-BIL-9005 · No reading counts ACCOUNTS, not meter rows", () => {
  it("one account with two unread meters is still 3 accounts on the pane line", async () => {
    mountRun({ twoUnreadMeters: true }, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    const pane = await openTagPane("No reading", "missing_read");
    await waitFor(() => expect(pane.querySelectorAll("[data-row-account]").length).toBe(4));
    expect(pane.querySelector("[data-pane-line]")).toHaveTextContent(/^3 accounts · /);
  });
});

describe("DEF-BIL-9006 · Estimate for all says why Price does not count it", () => {
  it("the bar names the missing figure while Estimate is the answer", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    const pane = await openTagPane("No reading", "missing_read");
    expect(pane.querySelector("[data-estimate-needs-figure]")).toHaveTextContent(
      "Estimate needs a figure per account. Or choose another answer.",
    );
  });
});

describe("DEF-BIL-9008 · a sent run's words", () => {
  it("the side card says bills sent, never draft bills", async () => {
    mountRun({ phase: "issued" }, OPEN_RUN);
    const card = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-run-summary] [data-aside-total]');
      expect(found).not.toBeNull();
      return found?.closest("[data-run-summary]") as HTMLElement;
    });
    await waitFor(() => expect(card).toHaveTextContent(/[\d,]+ bills sent/));
    expect(card).not.toHaveTextContent(/draft bills?/);
  });

  it("Not in this run says 1 unit, not 1 units", async () => {
    mountRun({ phase: "issued" }, OPEN_RUN);
    await screen.findByText(/5 accounts · 1 unit · pending/);
    expect(screen.queryByText(/1 units/)).toBeNull();
  });
});
