// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Screen:   S31 · BIL-02 — the bulk bill run, step 1 Scope
// Story:    US-BIL-036
// Defects:  DEF-BIL-8203 (Scope decided the standing answers) · DEF-BIL-8201
//           (Scope offered a which-services filter) · DEF-BIL-8202 (the live
//           Scope had no run name and no bill template)
// Rulings:  changes rows 11–14, 20 · BR-BIL-1040 as amended 2026-09-30
// ───────────────────────────────────────────────────────
/**
 * WHAT SCOPE ASKS, AND NOTHING ELSE.
 *
 * The PO moved the standing answers to Check, per problem type (2026-09-30,
 * *"move these choices to step 2 ... ths is correct"*), removed the services
 * filter (*"this filter is of now use"*) and put a required run name and bill
 * template on Scope. So the Scope step is exactly seven fields, it never
 * reads the standing-answer defaults, and the POST that starts the run
 * carries exactly those seven values — no `case_defaults`, no
 * `scope_services`.
 *
 * This asserts the WHOLE set rather than the absence of one named control,
 * because the thing that went wrong was a control being present; a test
 * that looks for one word misses the same control under another word.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CYCLE_ID } from "./__fixtures__/bulkRunFixtures";
import { mountRun } from "./__fixtures__/mountRun";

afterEach(cleanup);

const SCOPE_FIELDS = ["bill_date", "cycle_id", "due_days", "label", "period_end", "period_start", "template_id"];

async function chooseCycle() {
  const select = await screen.findByLabelText(/^Cycle/);
  await waitFor(() => expect(within(select).getAllByRole("option").length).toBeGreaterThan(1));
  fireEvent.change(select, { target: { value: CYCLE_ID } });
}

function formControls(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>("input, select, textarea")).filter(
    (el) => (el as HTMLInputElement).type !== "hidden",
  );
}

// BULK-CHG-10 (selection only) · BULK-CHG-11 (no services filter) · BULK-CHG-12 (bill template) ·
// BULK-CHG-13 (standing answers moved to Check) · BULK-CHG-14 (run name required) · BULK-CHG-27 (plan T4)
describe("DEF-BIL-8203 · Scope decides no standing answer", () => {
  it("Scope holds exactly the seven fields, run name and template required, and never reads the standing-answer defaults", async () => {
    const fake = mountRun();
    await chooseCycle();
    fireEvent.change(screen.getByLabelText(/^Run name/), { target: { value: "September 2026 · Riverside" } });
    await waitFor(() => expect(screen.getByRole("button", { name: "Start checking" })).toBeEnabled());

    const section = document.querySelector('[data-run-panel-section="what-to-bill"]') as HTMLElement;
    const inSection = formControls().filter((el) => section.contains(el));
    expect(inSection.map((el) => el.id).sort()).toEqual(SCOPE_FIELDS);
    // Outside the form, the only control is the Previous runs pager's
    // rows-per-page select: every option a page size.
    const outside = formControls().filter((el) => !section.contains(el));
    for (const el of outside) {
      expect(el.tagName).toBe("SELECT");
      const values = Array.from((el as HTMLSelectElement).options).map((option) => option.value);
      expect(values.every((value) => /^\d+$/.test(value))).toBe(true);
    }
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    expect(screen.queryAllByRole("checkbox")).toHaveLength(0);
    expect(screen.getByLabelText(/^Run name/)).toBeRequired();
    expect(screen.getByLabelText(/^Bill template/)).toBeRequired();
    expect(fake.calls.some((call) => call.path.includes("case-defaults"))).toBe(false);
  });

  it("Start sends the seven values and no case_defaults or scope_services", async () => {
    const fake = mountRun();
    await chooseCycle();
    fireEvent.change(screen.getByLabelText(/^Run name/), { target: { value: "September 2026 · Riverside" } });
    const start = screen.getByRole("button", { name: "Start checking" });
    await waitFor(() => expect(start).toBeEnabled());
    await act(async () => {
      fireEvent.click(start);
    });
    const post = await waitFor(() => {
      const found = fake.calls.find((call) => call.method === "POST" && call.path === "/billing/runs");
      expect(found).toBeDefined();
      return found;
    });
    expect(Object.keys(post?.body as Record<string, unknown>).sort()).toEqual(SCOPE_FIELDS);
  });
});
