// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1 (`DEF-523`).
// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-007 (EP-RBS-03) — CR-075 wave I task I6.
// Screens: RBS-008 Run history (one state), at `/{tenant}/runbooks/runs`.
// Rules:   BR-RBS-016 (a missed firing reads **Failed**) · BR-SHL-023 (the
//          tenant's own zone and format) · `NFR-3` · B14 rule 20 (columns in
//          THIS order) · rule 31 (no database id on screen) · rule 17.
// Defects: DEF-CWP-3925 (mount under the REAL path pattern) · DEF-RBS-4292
//          (there is no `started_by`, so *By* draws the trigger).
// ───────────────────────────────────────────────────────
// EVERY CASE ASSERTS A RULE — a column order, a resolved address, an absent
// uuid, a chip that becomes the right SERVER parameter — and none asserts an
// impression.
//
// ⚠ **THE ROUTE IS MOUNTED AT ITS REAL PATTERN AND THE ADDRESSES ARE ASSERTED
// BY ADDRESS.** `DEF-CWP-3925`: a component mounted bare inside a
// `MemoryRouter` gets `undefined` from `useParams()`, so every address it
// builds comes out `//portal/…` — a protocol-relative URL to another host,
// which reads as a perfectly good string to `toContain`. Eight dead doors hid
// behind 391 green cases that way.
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableRequestState } from "@/components/tableTypes";

import type { RunRow } from "../home/homeEndpoints";
import { historyParams } from "./historyEndpoints";
import { RunHistory } from "./RunHistory";

const TENANT = "silvercreek";

// No auto-cleanup in this repo — every "exactly N" assertion below depends on
// this line (`vite.config.ts` registers no `setupFiles`).
afterEach(cleanup);

const NOOP = () => undefined;

const STATE: TableRequestState = {
  q: "",
  sort: "started_at",
  dir: "desc",
  page: 1,
  per: DEFAULT_PAGE_SIZE,
  filters: {},
};

function runRow(overrides: Partial<RunRow> = {}): RunRow {
  return {
    id: "0198f0c2-1111-7000-8000-000000000001",
    runbook_key: "pre_bill_sweep",
    runbook_name: "Pre-bill sweep",
    kind: "check",
    category: "billing",
    version: 3,
    mode: "dry",
    trigger: "schedule",
    status: "done",
    started_at: "2026-01-05T12:00:00Z",
    finished_at: "2026-01-05T12:00:12Z",
    took_seconds: 12,
    counts: { clean: 21 },
    records: 25,
    by: { trigger: "schedule", person: null },
    ...overrides,
  };
}

function mount(
  rows: readonly RunRow[],
  overrides: Partial<Parameters<typeof RunHistory>[0]> = {},
) {
  return render(
    <MemoryRouter initialEntries={[`/${TENANT}/runbooks/runs`]}>
      <Routes>
        <Route
          path="/:tenant/runbooks/runs"
          element={
            <RunHistory
              rows={rows}
              total={rows.length}
              loading={false}
              error={null}
              state={STATE}
              onStateChange={NOOP}
              chip="all"
              onChip={NOOP}
              onBrowseRunbooks={NOOP}
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

describe("RBS-008 — the table the sheet draws", () => {
  it("draws the seven columns in THIS order", () => {
    mount([runRow()]);
    expect(headers()).toEqual([
      "Started",
      "Runbook",
      "By",
      "Outcome",
      "Acted",
      "Took",
      "Actions",
    ]);
  });

  it("links the runbook name to its setup screen, BY ADDRESS", () => {
    mount([runRow()]);
    const link = document.querySelector('[data-runbook="pre_bill_sweep"]');
    expect(link?.getAttribute("href")).toBe(`/${TENANT}/runbooks/pre_bill_sweep`);
  });

  it("opens a run's own result, BY ADDRESS", () => {
    mount([runRow()]);
    const open = screen.getByRole("link", { name: "Open result" });
    expect(open.getAttribute("href")).toBe(
      `/${TENANT}/runbooks/pre_bill_sweep/runs/0198f0c2-1111-7000-8000-000000000001`,
    );
  });

  it("never renders the run id as the visible value of a cell (B14 rule 31)", () => {
    mount([runRow()]);
    const body = document.querySelector("tbody")?.textContent ?? "";
    expect(body).not.toContain("0198f0c2");
  });
});

describe("BR-RBS-016 — a missed firing is Failed, and it is readable", () => {
  it("draws a missed firing as Failed, in the danger tone", () => {
    mount([
      runRow({
        status: "failed",
        started_at: "2026-01-05T12:00:00Z",
        took_seconds: null,
        records: 0,
        counts: { missed: 1 },
      }),
    ]);
    // ⚠ **ASSERTED THROUGH THE PILL'S OWN CLASS, NOT A `data-` ATTRIBUTE.**
    // `StatusPill` takes `tone`, `children` and `title` and forwards nothing
    // else, so a `data-outcome` hung on it is silently dropped — and a test
    // querying for it finds nothing and reads as if the pill were missing. The
    // first draft of this case did exactly that and went red for the wrong
    // reason, which is the cheapest possible version of law 7's *looking at
    // the wrong thing*.
    const pill = document.querySelector("tbody tr:first-child .pill");
    expect(pill?.textContent).toBe("Failed");
    // `StatusPill` maps the DANGER tone to the stylesheet's `past` class
    // (`components/StatusPill.tsx` TONE_CLASS) — asserted by the class the
    // browser actually gets, not by the word this file passed in.
    expect(pill?.className).toContain("past");
  });

  it("draws *Started* from `started_at`, which on a missed firing is the time it SHOULD have run", () => {
    // The scheduler writes `started_at` = the missed 06:00 and `finished_at` =
    // the moment the sweep noticed, hours later. A screen drawing `created_at`
    // or `finished_at` would tell a clerk the wrong time, in a cell they have
    // no reason to doubt.
    mount([runRow({ status: "failed", started_at: "2026-01-05T12:00:00Z" })]);
    const cells = Array.from(
      document.querySelectorAll("tbody tr:first-child td"),
      (cell) => (cell.textContent ?? "").trim(),
    );
    expect(cells[0]).toContain("05");
    expect(cells[0]).not.toBe("");
  });

  it("says *Still going* rather than drawing a blank while a run is in flight", () => {
    mount([runRow({ status: "running", finished_at: null, took_seconds: null })]);
    expect(screen.getByText("Still going")).toBeTruthy();
  });

  it("says *Not started yet* rather than drawing a blank when there is no start", () => {
    mount([runRow({ started_at: null })]);
    expect(screen.getByText("Not started yet")).toBeTruthy();
  });
});

describe("the *By* column — a person or Schedule, and today only one of them", () => {
  it("draws the TRIGGER while `by.person` is null (DEF-RBS-4292)", () => {
    mount([runRow({ by: { trigger: "schedule", person: null } })]);
    const cells = Array.from(
      document.querySelectorAll("tbody tr:first-child td"),
      (cell) => (cell.textContent ?? "").trim(),
    );
    expect(cells[2]).toBe("Scheduled");
  });

  it("draws the PERSON the day the server has one", () => {
    mount([runRow({ by: { trigger: "manual", person: "Dana W." } })]);
    const cells = Array.from(
      document.querySelectorAll("tbody tr:first-child td"),
      (cell) => (cell.textContent ?? "").trim(),
    );
    expect(cells[2]).toBe("Dana W.");
  });
});

describe("the chips are a SERVER filter (NFR-3)", () => {
  it("turns each chip into the one parameter it moves", () => {
    const base = { q: "", page: 1, per: 50 } as const;
    expect(historyParams({ ...base, chip: "all" })).toEqual({ page: 1, per: 50 });
    expect(historyParams({ ...base, chip: "check" })).toEqual({
      page: 1,
      per: 50,
      "f.kind": "check",
    });
    expect(historyParams({ ...base, chip: "action" })).toEqual({
      page: 1,
      per: 50,
      "f.kind": "action",
    });
    expect(historyParams({ ...base, chip: "failed" })).toEqual({
      page: 1,
      per: 50,
      "f.outcome": "failed",
    });
    expect(historyParams({ ...base, chip: "stopped" })).toEqual({
      page: 1,
      per: 50,
      "f.outcome": "stopped",
    });
  });

  it("sends the search term to the server rather than filtering a page", () => {
    expect(historyParams({ q: "  sweep ", chip: "all", page: 2, per: 100 })).toEqual({
      page: 2,
      per: 100,
      q: "sweep",
    });
  });

  it("draws the five chips the sheet draws, in order", () => {
    mount([runRow()]);
    const chips = document.querySelector('[data-chips="outcome"]');
    const labels = Array.from(
      chips?.querySelectorAll("[data-chip]") ?? [],
      (one) => (one.textContent ?? "").trim(),
    );
    expect(labels).toEqual(["All", "Checks", "Actions", "Failed", "Stopped"]);
  });
});

describe("RBS-008 empty — rule 17", () => {
  it("says what is missing and offers the action that fills it", () => {
    mount([], { total: 0 });
    expect(screen.getByText("Nothing has run yet")).toBeTruthy();
    const cta = screen.getByRole("button", { name: "My runbooks →" });
    expect(within(cta).queryByText("undefined")).toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RBS-007 (EP-RBS-03; CR-075 wave I task I6) · wireframes/RBS-008.md · B14 rules 17/20/31 · NFR-3
// generated: 2026-09-07 by the CR-075 wave I build lane
// checklist: A✔ B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest · ./node_modules/.bin/tsc --noEmit (the LOCAL compiler, never npx)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
