// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1 (`DEF-523`).
// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-003 (EP-RBS-01) — CR-075 wave D task D4.
// Screens: RBS-003.1 all · RBS-003.2 filtered to Actions · RBS-003.3 empty.
// Rules:   B14 rule 17 (an empty list says what is missing and the action that
//          fills it) · rule 20 (columns in THIS order) · rule 31 (no database
//          id on screen) · `NFR-3`.
// Defects: DEF-CWP-3925 (mount under the REAL path pattern) · DEF-RBS-4291
//          (`started_at` is never stamped) · DEF-RBS-4310.
// ───────────────────────────────────────────────────────
// EVERY CASE ASSERTS A RULE — a column order, a resolved address, a missing
// uuid — and none asserts an impression.
//
// ⚠ **THE ADDRESS ASSERTIONS ARE THE POINT OF THIS FILE.** `RBS-004` shipped in
// wave C with **no door**: the decision log of 2026-09-06 says *"nothing in the
// product points at it … the door is `RBS-003` (My runbooks, task `D4`)."* This
// screen is that door, so its links are asserted **by address**, never by *there
// is a link* — `DEF-CWP-3925`'s dead `//portal/…` hrefs were perfectly good
// strings to `toContain`, and eight doors hid behind 391 green cases.
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableRequestState } from "@/components/tableTypes";

import { MyRunbooks } from "./MyRunbooks";
import { THREE_RUNBOOKS, catalogueRow } from "./libraryFixture";
import type { CatalogueRow } from "./libraryTypes";

const TENANT = "silvercreek";

// No auto-cleanup in this repo — every "exactly N" assertion below depends on
// this line (`vite.config.ts` registers no `setupFiles`).
afterEach(cleanup);

const NOOP = () => undefined;

const STATE: TableRequestState = {
  q: "",
  sort: "name",
  dir: "asc",
  page: 1,
  per: DEFAULT_PAGE_SIZE,
  filters: {},
};

function mount(
  rows: readonly CatalogueRow[],
  overrides: Partial<Parameters<typeof MyRunbooks>[0]> = {},
) {
  return render(
    <MemoryRouter initialEntries={[`/${TENANT}/runbooks/mine`]}>
      <Routes>
        <Route
          path="/:tenant/runbooks/mine"
          element={
            <MyRunbooks
              rows={rows}
              total={rows.length}
              loading={false}
              error={null}
              state={STATE}
              onStateChange={NOOP}
              kind=""
              onKind={NOOP}
              templatesTo={`/${TENANT}/runbooks/templates`}
              onBrowseTemplates={NOOP}
              onClone={NOOP}
              {...overrides}
            />
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

function headers(): string[] {
  return Array.from(document.querySelectorAll("thead th"), (cell) =>
    (cell.textContent ?? "").trim(),
  );
}

describe("RBS-003.1 — the table the sheet draws", () => {
  it("draws the eight columns in THIS order", () => {
    mount(THREE_RUNBOOKS);
    // `08-screen-layouts.md`, word for word: *"Runbook (sortable) · Kind ·
    // Category · Schedule · Last run (sortable) · Result · Open items (numeric,
    // right) · row actions."* B14 rule 20 makes the ORDER part of the rule.
    expect(headers()).toEqual([
      "Runbook",
      "Kind",
      "Category",
      "Schedule",
      "Last run",
      "Result",
      "Open items",
      "Actions",
    ]);
  });

  it("declares NO column sortable, because the server sorts none", () => {
    mount(THREE_RUNBOOKS);
    // `apps/runbooks/api.py` calls `parse_list_params(..., allowed_sorts=())`,
    // so a `sort` param is ignored. A chevron a person can press that changes
    // nothing is law 7's *structurally incapable of failing* wearing a control.
    expect(document.querySelectorAll("thead th button")).toHaveLength(0);
  });

  it("sends every runbook name to its setup screen, by address", () => {
    mount(THREE_RUNBOOKS);
    const link = document.querySelector('[data-runbook="collections_ladder"]');
    expect(link?.getAttribute("href")).toBe(`/${TENANT}/runbooks/collections_ladder`);
  });

  it("shows no database id anywhere on the screen", () => {
    mount(THREE_RUNBOOKS);
    // B14 rule 31, ratified in the PO's own words: *"no Databse ID on screen -
    // that is a rule."* The run ids ARE in the markup — as the `href` of the
    // view-last-run action, which is an address rather than a drawn value — so
    // this asserts the TEXT rather than the whole document.
    const body = document.querySelector("tbody");
    expect(body?.textContent ?? "").not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/);
  });

  it("says Not started yet rather than drawing a blank Last run", () => {
    mount(THREE_RUNBOOKS);
    // `DEF-RBS-4291`: `services.open_run` never stamps `started_at`, so this
    // reads on every row of every tenant today. A blank cell would read as a
    // screen that failed to load; the words say which it is.
    expect(screen.getAllByText("Not started yet")).toHaveLength(2);
    // …and the runbook that has never run says THAT instead, which is a
    // different fact.
    const rows = document.querySelectorAll("tbody tr");
    expect(within(rows[2] as HTMLElement).getAllByText("Never run").length).toBeGreaterThan(0);
  });

  it("reads Paused from `enabled`, whatever the trigger says", () => {
    mount(THREE_RUNBOOKS);
    const rows = document.querySelectorAll("tbody tr");
    // Row 3 is `schedule`-triggered AND disabled. A paused runbook does not run
    // whatever its trigger says, and that is the fact a clerk scanning this
    // column is looking for.
    expect(within(rows[2] as HTMLElement).getByText("Paused")).not.toBeNull();
    expect(within(rows[0] as HTMLElement).getByText("Manual")).not.toBeNull();
  });

  it("carries the open-item count — the column that makes the screen worth opening", () => {
    mount(THREE_RUNBOOKS);
    const rows = document.querySelectorAll("tbody tr");
    const cells = (rows[1] as HTMLElement).querySelectorAll("td");
    expect((cells[6].textContent ?? "").trim()).toBe("6");
  });

  it("disables the view action with its reason on a runbook that never ran", () => {
    mount(THREE_RUNBOOKS);
    const rows = document.querySelectorAll("tbody tr");
    const action = within(rows[2] as HTMLElement).getByRole("button", {
      name: "View last run",
    }) as HTMLButtonElement;
    // `BR-SHL-025`: the reason travels ON the control, so a person learns the
    // rule instead of hunting for a control somebody removed.
    expect(action.disabled).toBe(true);
    expect(action.getAttribute("title")).toBe("Never run");
  });

  it("opens the last run at the run-result address when there is one", () => {
    mount(THREE_RUNBOOKS);
    const rows = document.querySelectorAll("tbody tr");
    const link = within(rows[0] as HTMLElement).getByRole("link", { name: "View last run" });
    expect(link.getAttribute("href")).toBe(
      `/${TENANT}/runbooks/configuration_check/runs/0192f3aa-0000-7000-8000-000000000001`,
    );
  });
});

describe("RBS-003.2 — filtered to Actions, on the SERVER", () => {
  it("asks the server for the kind rather than filtering these rows", () => {
    const onKind = vi.fn();
    mount(THREE_RUNBOOKS, { onKind });
    (document.querySelector('[data-kind="action"]') as HTMLElement).click();
    // `NFR-3`. A screen narrowing its own page would be right on page 1 and
    // wrong on page 2.
    expect(onKind).toHaveBeenCalledWith("action");
  });

  it("draws the selected chip with its × and clears on a second press", () => {
    const onKind = vi.fn();
    mount(THREE_RUNBOOKS, { kind: "action", onKind });
    const chip = document.querySelector('[data-kind="action"]') as HTMLElement;
    // *A filter is visible and undoable* — the sheet draws the chip with its ×.
    expect(chip.getAttribute("aria-pressed")).toBe("true");
    expect(chip.textContent).toContain("×");
    chip.click();
    expect(onKind).toHaveBeenCalledWith("");
  });

  it("draws only the three chips the server can answer", () => {
    mount(THREE_RUNBOOKS);
    // `DEF-RBS-4310`: the sheet also draws `Scheduled` and `Paused`, and the
    // catalogue endpoint filters on neither. Absent rather than dead.
    const kinds = Array.from(document.querySelectorAll("[data-kind]"), (chip) =>
      chip.getAttribute("data-kind"),
    );
    expect(kinds).toEqual(["all", "check", "action"]);
  });
});

describe("RBS-003.3 — the empty state", () => {
  it("names what is missing and the action that fills it", () => {
    mount([]);
    // B14 rule 17, and the sheet's own copy.
    expect(screen.getByText("No runbooks yet")).not.toBeNull();
    expect(screen.getByText("Add one from templates.")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Browse templates →" })).not.toBeNull();
  });

  it("wires that button to something — it is not a decoration", () => {
    const onBrowseTemplates = vi.fn();
    mount([], { onBrowseTemplates });
    screen.getByRole("button", { name: "Browse templates →" }).click();
    // Hard-won law 2: a control with an optional handler nothing passes renders,
    // passes every test, and does nothing. The prop is required and this is the
    // case that proves it reaches a caller.
    expect(onBrowseTemplates).toHaveBeenCalledTimes(1);
  });

  it("keeps ONE primary on the screen — the head's, not the empty state's", () => {
    mount([]);
    // B14 rule 4. Work > Parts shipped two primaries and the PO reported it as
    // *"two + Add part buttons"*.
    const primaries = document.querySelectorAll('[data-variant="primary"]');
    expect(primaries).toHaveLength(1);
    expect(primaries[0].getAttribute("href")).toBe(`/${TENANT}/runbooks/templates`);
  });
});

describe("the page head", () => {
  it("exits to the runbooks home and offers Templates →", () => {
    mount([catalogueRow("configuration_check", "Can we bill?")]);
    const back = screen.getByRole("link", { name: /Runbooks/ });
    expect(back.getAttribute("href")).toBe(`/${TENANT}/runbooks`);
    expect(document.querySelector("[data-templates]")?.getAttribute("href")).toBe(
      `/${TENANT}/runbooks/templates`,
    );
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-003 (EP-RBS-01; CR-075 wave D task D4) · wireframes/RBS-003.1–.3 · 08-screen-layouts.md §RBS-003 · B14 rules 4/17/20/31
// generated: 2026-09-06 by the CR-075 wave D D3/D4 build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: RED PROVED FIRST through ./node_modules/.bin/vitest — the first column relabelled failed "draws the eight columns in THIS order" with «expected [ 'Kind', 'Kind', 'Category', …(5) ] to deeply equal [ 'Runbook', 'Kind', 'Category', …(5) ]», and the empty-state CTA rewired to a no-op failed "wires that button to something" with «expected "spy" to be called 1 times, but got 0 times»; both restored and re-run green · tsc --noEmit (the LOCAL compiler)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
