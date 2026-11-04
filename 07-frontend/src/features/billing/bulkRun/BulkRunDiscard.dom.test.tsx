// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-BIL-9255 — a draft bill run could not be thrown away, so a run
//          made for the wrong period blocked every overlapping run.
// Rules:   BR-BIL-1045 (`abandoned`) · B14 rule 6 (danger tier on a
//          destructive confirm) · B14 rule 33 (≤ 6 words a sentence)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RUN_ID } from "./__fixtures__/bulkRunFixtures";
import { mountRun, where } from "./__fixtures__/mountRun";

afterEach(cleanup);

describe("DEF-BIL-9255 · Discard a draft run", () => {
  it("a draft run offers Discard run; the confirm is danger tier and posts the discard, then the page leaves the run", async () => {
    const fake = mountRun({ phase: "draft" }, `?run=${RUN_ID}`);
    const button = await screen.findByRole("button", { name: "Discard run" });
    fireEvent.click(button);
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText("Discard this run?")).toBeInTheDocument();
    expect(within(dialog).getByText("Its draft bills are deleted. This cannot be undone.")).toBeInTheDocument();
    const confirm = within(dialog).getByRole("button", { name: "Discard run" });
    expect(confirm).toHaveAttribute("data-variant", "danger");
    fireEvent.click(confirm);
    await waitFor(() =>
      expect(fake.calls.some((call) => call.method === "POST" && call.path === `/billing/runs/${RUN_ID}/discard`)).toBe(true),
    );
    await waitFor(() => expect(where.location).not.toContain(`run=${RUN_ID}`));
  });

  it("an issued run offers no Discard", async () => {
    mountRun({ phase: "issued" }, `?run=${RUN_ID}`);
    await screen.findAllByText(/./);
    await waitFor(() => expect(document.querySelector("[data-run-line]")).not.toBeNull());
    expect(screen.queryByRole("button", { name: "Discard run" })).toBeNull();
  });

  it("an authorised (signed-off) run offers no Discard", async () => {
    mountRun({ phase: "authorised" }, `?run=${RUN_ID}`);
    await waitFor(() => expect(document.querySelector("[data-run-line]")).not.toBeNull());
    expect(screen.queryByRole("button", { name: "Discard run" })).toBeNull();
  });
});
