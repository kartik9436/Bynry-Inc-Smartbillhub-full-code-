// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Screen:   S31 · BIL-02 — the bulk bill run
// Journey:  J72 § E11 wave 3 — the last eight states that differed from D1
// Defects:  DEF-BIL-8691 (04) · DEF-BIL-8701 (11–14) · DEF-BIL-8682 (25, 28) ·
//           DEF-BIL-8685 (35), as each `describe` names
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/ (the image each case names)
// ───────────────────────────────────────────────────────
/**
 * THE THIRD WAVE OF E11: EACH DIFFERENCE WAITED ON A FIELD THE SERVER DID NOT
 * SEND. The fixtures now serve each field the way the server does; every case
 * was written to fail on 2.422.0 and names the drawing it is held to.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";
import type { ScopeProblem } from "@/api/bulkRunEndpoints";

import { CYCLE_ID, RUN_ID } from "./__fixtures__/bulkRunFixtures";
import { mountRun } from "./__fixtures__/mountRun";
import { problemMessage } from "./ScopeStep";

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

async function chooseCycleNow(): Promise<void> {
  const cycle = await screen.findByLabelText(/^Cycle/);
  await waitFor(() => expect(cycle.querySelectorAll("option").length).toBeGreaterThan(1));
  fireEvent.change(cycle, { target: { value: CYCLE_ID } });
}

describe("DEF-BIL-8691 · the period line says the cycle's frequency (D1 04)", () => {
  it("'45 days. Cycle is monthly. Ends after today.'", async () => {
    mountRun({ scope: "serverOrder" });
    await chooseCycleNow();
    const period = await waitFor(() => {
      const found = Array.from(
        document.querySelectorAll<HTMLElement>('[data-run-problems="warning"] [data-problem-line]'),
      ).find((line) => (line.dataset.problemLine ?? "").startsWith("period_length"));
      expect(found).toBeDefined();
      return found as HTMLElement;
    });
    expect(period).toHaveTextContent("45 days. Cycle is monthly. Ends after today.");
    expect(period).not.toHaveTextContent("Cycle expects");
    // …and the note under Period end carries the whole line too, as drawn.
    expect(document.querySelector('[data-field-warning="period_end"]')).toHaveTextContent(
      /^45 days\. Cycle is monthly\. Ends after today\.$/,
    );
  });

  it("a frequency the catalogue has no word for keeps the day count, never a raw code", () => {
    const fmt = { t: i18n.t.bind(i18n), dateFormat: "MM/DD/YYYY", currency: "USD", timeZone: "America/Chicago" } as never;
    const problem = (frequency: unknown): ScopeProblem =>
      ({
        code: "period_length",
        severity: "warning",
        field: "period_end",
        message_key: "billing.runScope.warning.periodLength",
        params: { days: 45, expected: 30, frequency },
      }) as ScopeProblem;
    expect(problemMessage(problem("Quarterly"), fmt)).toBe("45 days. Cycle is quarterly.");
    expect(problemMessage(problem("Fortnightly"), fmt)).toBe("45 days. Cycle is biweekly.");
    expect(problemMessage(problem("Lunar"), fmt)).toBe("45 days. Cycle expects 30.");
    expect(problemMessage(problem(null), fmt)).toBe("45 days. Cycle expects 30.");
  });
});

describe("DEF-BIL-8701 · a Check row names its meter beside the service (D1 11–14)", () => {
  it("the Service cell reads 'Water · W-10441'", async () => {
    mountRun({}, OPEN_RUN);
    await screen.findByText(/Checked 1,406 accounts at/);
    const pane = await openTagPane("No reading", "missing_read");
    const row = await waitFor(() => {
      const found = pane.querySelector<HTMLElement>('[data-row-account="AC-2026-12881"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    const cells = Array.from(row.querySelectorAll("td")).map((td) => td.textContent);
    expect(cells).toContain("Water · W-10441");
  });
});

describe("DEF-BIL-8682 · Sign off parts payments from credits (D1 25, 28)", () => {
  it("the tile is the payments with their count; the table has a line each", async () => {
    mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    const card = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-run-facts="run-summary"] [data-run-fact="payments"]');
      expect(found).not.toBeNull();
      // DEF-BIL-8809 — the card is drawn before Sign off's figures arrive (its
      // other reads now start beside the run read); wait for the figure itself.
      expect(found).toHaveTextContent(/Payments applied\s*\$25,260\.51\s*1,840 payments/);
      return found as HTMLElement;
    });
    expect(card).toHaveTextContent(/Payments applied\s*\$25,260\.51\s*1,840 payments/);
    const balances = document.querySelector('[data-run-table="balances"]') as HTMLElement;
    const paid = balances.querySelector('[data-who-row="paid"]') as HTMLElement;
    expect(paid).toHaveTextContent(/^Payments applied\s*1,840\s*−\$25,260\.51$/);
    const credits = balances.querySelector('[data-who-row="credits"]') as HTMLElement;
    expect(credits).toHaveTextContent(/Credits applied\s*41\s*−\$1,215\.60/);
    expect(balances).not.toHaveTextContent("Payments and credits");
  });
});

describe("DEF-BIL-8685 · the Sent card says the meter reads are locked (D1 35)", () => {
  it("'Meter reads  Locked' under Delivery", async () => {
    mountRun({ phase: "issued" }, OPEN_RUN);
    await screen.findByText("1,369 bills sent");
    const row = await waitFor(() => {
      const found = document.querySelector<HTMLElement>('[data-sent-card] [data-sent-row="meter-reads"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(row).toHaveTextContent(/^Meter reads\s*Locked$/);
  });
});
