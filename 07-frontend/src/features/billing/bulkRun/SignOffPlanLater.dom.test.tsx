// @vitest-environment jsdom
/**
 * DEF-BIL-8720 — Sign off's Amount due asks what the bills will ask.
 *
 * PO ruling 1 of 2026-10-01 (BR-BIL-1061): a bill on a payment plan asks the
 * new charges and this month's instalment — $62 + $45 = $107 — and shows the
 * rest of the plan as not yet due. The server now takes that part off Sign
 * off's Amount due too, and serves it as `plan_not_yet_due`; the balances
 * table draws it as its own line, so Previous − Payments + Charges − Plan
 * later = Amount due foots on screen. No figure is worked out in the browser
 * (CLAUDE.md rule 2): every number below is the server's.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RUN_ID } from "./__fixtures__/bulkRunFixtures";
import { mountRun } from "./__fixtures__/mountRun";

const OPEN_RUN = `?run=${RUN_ID}`;

afterEach(cleanup);

function balances(): HTMLElement {
  const table = document.querySelector<HTMLElement>('[data-run-table="balances"]');
  expect(table).not.toBeNull();
  return table as HTMLElement;
}

describe("DEF-BIL-8720 · a payment plan's part not yet due on Sign off", () => {
  it("draws 'Plan, due later' taken off, and the Amount due the bills will ask", async () => {
    mountRun({ phase: "calculated", planLater: true }, OPEN_RUN);
    await screen.findByText("Run summary");
    await waitFor(() => expect(balances().querySelector('[data-who-row="plan-later"]')).not.toBeNull());
    const later = balances().querySelector('[data-who-row="plan-later"]') as HTMLElement;
    expect(later).toHaveTextContent(/Plan, due later\s*−\$225\.00/);
    const due = balances().querySelector('[data-who-row="due"]') as HTMLElement;
    expect(due).toHaveTextContent("$235,895.41");
    // the line sits between this run's charges and the amount due
    const order = Array.from(balances().querySelectorAll("[data-who-row]")).map((row) => (row as HTMLElement).dataset.whoRow);
    expect(order.indexOf("plan-later")).toBe(order.indexOf("due") - 1);
    expect(order.indexOf("charges")).toBeLessThan(order.indexOf("plan-later"));
  });

  it("draws no plan line when no bill holds any back", async () => {
    mountRun({ phase: "calculated" }, OPEN_RUN);
    await screen.findByText("Run summary");
    await waitFor(() => expect(balances().querySelector('[data-who-row="due"]')).not.toBeNull());
    expect(balances().querySelector('[data-who-row="plan-later"]')).toBeNull();
    expect(balances().querySelector('[data-who-row="due"]')).toHaveTextContent("$236,120.41");
  });
});
