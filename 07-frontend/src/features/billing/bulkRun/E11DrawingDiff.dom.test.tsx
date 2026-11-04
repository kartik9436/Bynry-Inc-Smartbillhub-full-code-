// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Screen:   S31 · BIL-02 — the bulk bill run, Scope (D1 01–07) and Check (D1 16)
// Journey:  J72 § E11 — the screens put beside the D1 drawings, 2026-10-01
// Defects:  DEF-BIL-8672 (`1 units have nobody to bill.`) · DEF-BIL-8673 (problem
//           lines in the server's order, not the form's) · DEF-BIL-8674 (Paid
//           after cut-off offered `Put it on this bill` for the NEXT-bill answer)
// Drawing:  05-prototype/bulk-bill-run-2026-09-30/02, 04 (field order), 16 (`Next bill`)
// ───────────────────────────────────────────────────────
/**
 * THREE THINGS E11 SAW ONLY BY PUTTING THE LIVE SCREEN BESIDE ITS DRAWING.
 *
 * Each was invisible to the tests that already existed, because those tests
 * asserted that a line or an answer was PRESENT, never what it SAID or where it
 * stood. These assert the words and the order.
 *
 * `apply_next_bill` is one engine choice code shared by two cases with opposite
 * readings of "this bill": for a true-up it means the trued-up quantity goes on
 * THIS bill (`Put it on this bill` is right there), for a payment that arrived
 * after the cut-off it means the payment goes to the NEXT bill. The pane offered
 * `Apply to this bill` and `Put it on this bill` side by side — two answers a
 * clerk cannot tell apart, one of which does the opposite of what it says.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import { choiceLabel } from "./CheckPanes";
import { CYCLE_ID } from "./__fixtures__/bulkRunFixtures";
import { mountRun } from "./__fixtures__/mountRun";

afterEach(cleanup);

const t = i18n.t.bind(i18n) as unknown as Parameters<typeof choiceLabel>[1];

async function chooseCycle() {
  const select = await screen.findByLabelText(/^Cycle/);
  await waitFor(() => expect(within(select).getAllByRole("option").length).toBeGreaterThan(1));
  fireEvent.change(select, { target: { value: CYCLE_ID } });
}

function warningLines(): HTMLElement[] {
  const box = document.querySelector('[data-run-problems="warning"]');
  return box === null ? [] : Array.from(box.querySelectorAll<HTMLElement>("[data-problem-line]"));
}

describe("J72 E11 · Scope's problem box, beside D1 02 and 04", () => {
  it("DEF-BIL-8672 · one unit reads '1 unit has nobody to bill.', one service '1 service has no meter.'", async () => {
    mountRun({ scope: "serverOrder" });
    await chooseCycle();
    await waitFor(() => expect(warningLines().length).toBe(5));
    const text = warningLines().map((line) => line.textContent ?? "");
    expect(text.some((line) => line.includes("1 unit has nobody to bill."))).toBe(true);
    expect(text.some((line) => line.includes("1 service has no meter."))).toBe(true);
    expect(text.join(" ")).not.toMatch(/\b1 units\b|\b1 services\b/);
  });

  it("DEF-BIL-8673 · lines follow the form's field order, count lines last, whatever order the server sent", async () => {
    mountRun({ scope: "serverOrder" });
    await chooseCycle();
    await waitFor(() => expect(warningLines().length).toBe(5));
    const codes = warningLines().map((line) => (line.dataset.problemLine ?? "").replace(/-\d+$/, ""));
    // Since DEF-BIL-8691 the two Period end warnings read as ONE line.
    expect(codes).toEqual([
      "period_length",
      "bill_day_differs",
      "due_days_changed",
      "units_nobody_to_bill",
      "services_no_meter",
    ]);
    expect(screen.getAllByText("Period end").length).toBeGreaterThan(0);
  });
});

describe("J72 E11 · Check's Paid after cut-off answers, beside D1 16", () => {
  it("DEF-BIL-8674 · the next-bill answer reads 'Next bill' and can never read as 'this bill'", () => {
    const next = choiceLabel("apply_next_bill", t, "paid_after_cutoff");
    const now = choiceLabel("apply_this_bill", t, "paid_after_cutoff");
    expect(next).toBe("Next bill");
    expect(next).not.toMatch(/this bill/i);
    expect(next).not.toBe(now);
  });

  it("DEF-BIL-8674 · a true-up keeps its own reading of the shared code (the trued-up quantity goes on THIS bill)", () => {
    expect(choiceLabel("apply_next_bill", t, "true_up")).toBe("Put it on this bill");
  });
});
