// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1. `vite.config.ts` keeps
// the default environment at `node` deliberately (`DEF-523`); an interactive
// suite opts in per file, and without this line every case here dies on
// `ReferenceError: document is not defined` — which is how this file first ran.
/* ══════════════════════════════════════════════════════════════════════════
 * CR-075 wave H · H3 — `RBS-007`, the work list
 * ══════════════════════════════════════════════════════════════════════════
 * Assertions are what a READER sees, from `wireframes/RBS-007.1___RBS-007.2`'s
 * own words, plus the two structural ones that go red on a real mistake:
 *
 *   · **the AGE is the FIRST sighting** — a row 30 days old reads *30 days*
 *     however recently the sweep last saw it, which is the whole argument of
 *     `US-RBS-006` and the one number a `updated_at` cell would destroy;
 *   · **the addresses are the TENANT's** — every link is asserted as a WHOLE
 *     href. `DEF-CWP-3925`: a component mounted bare in a `MemoryRouter` gets
 *     `undefined` for `:tenant` and builds `//host/…`, which reads as a
 *     perfectly good string to `toContain`; and `DEF-RBS-4329`: a href that
 *     merely ENDS with the route is satisfied by a wrongly prefixed one.
 * ══════════════════════════════════════════════════════════════════════════ */
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

// ⚠ **THE REAL CATALOGUE, NOT A STUB.** Without it `t()` returns the KEY and
// every assertion in this file would be about `work.col.what` rather than about
// *What needs doing* — a suite that passes over a screen whose copy nobody has
// written. `TemplateLibrary.dom.test.tsx` imports it for the same reason.
import "@/i18n";

import { tenantPathFrom } from "@/routing/tenantPath";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableRequestState } from "@/components/tableTypes";

import { ageWords, WorkList } from "./WorkList";
import type { WorkItemRow } from "./workTypes";

// ⚠ **THIS SUITE REGISTERS ITS OWN `cleanup`, AND `jest-dom` IS NOT LOADED.**
// `vite.config.ts` declares no `setupFiles`, so `@testing-library/react`
// registers no `afterEach` of its own — a second `render` in one file leaves
// the first still mounted, and every `getByText` then fails with *found
// multiple elements*, which reads like a duplicated row rather than a missing
// teardown. And `toBeInTheDocument` is *Invalid Chai property* rather than a
// failure: a matcher that does not exist THROWS where a reader expects an
// assertion. So everything below asserts on the node itself. Both were found
// by running this file, not by reading it.
afterEach(cleanup);

const TENANT = "brazosbend";
/** The address this screen is actually served at. */
const WORK_PATH = `/${TENANT}/runbooks/work`;
/** A fixed day, so the Age column is a fact rather than a function of when the
 *  suite happened to run (gate `G6`, `BR-TEN-043`'s spirit). */
const TODAY = new Date("2026-09-07T09:00:00Z");

const STATE: TableRequestState = {
  q: "",
  sort: "weight",
  dir: "desc",
  page: 1,
  per: DEFAULT_PAGE_SIZE,
  filters: {},
};

const TAX_REGION: WorkItemRow = {
  id: "11111111-1111-1111-1111-111111111111",
  source_kind: "finding",
  from: "Can we bill?",
  run_id: "22222222-2222-2222-2222-222222222222",
  runbook_key: "configuration_check",
  title: "No tax region is set, so nothing on this service can be taxed.",
  subject_ref: "240 accounts",
  weight: 100,
  weight_pill: "blocks_billing",
  fix_route: "settings/tax",
  owner: "Dana W.",
  owner_id: "33333333-3333-3333-3333-333333333333",
  due_on: null,
  status: "open",
  // Thirty days before TODAY.
  created_at: "2026-08-08T09:00:00Z",
  resolved_at: null,
};

const SIGN_THE_LAYOUT: WorkItemRow = {
  id: "44444444-4444-4444-4444-444444444444",
  source_kind: "human_task",
  from: null,
  run_id: null,
  runbook_key: null,
  title: "Customer signs bill layout",
  subject_ref: null,
  weight: 0,
  weight_pill: "human_task",
  fix_route: null,
  owner: null,
  owner_id: null,
  due_on: null,
  status: "open",
  created_at: "2026-09-07T06:00:00Z",
  resolved_at: null,
};

function draw(props: Partial<Parameters<typeof WorkList>[0]> = {}) {
  const onResolve = vi.fn();
  const onReopen = vi.fn();
  const onChip = vi.fn();
  render(
    // ⚠ **UNDER THE REAL PATH PATTERN** — `DEF-CWP-3925`. Mounted bare, every
    // address this screen builds would come out `//brazosbend/…`.
    <MemoryRouter initialEntries={[WORK_PATH]}>
      <Routes>
        <Route
          path="/:tenant/runbooks/work"
          element={
            <WorkList
              rows={[TAX_REGION, SIGN_THE_LAYOUT]}
              total={2}
              loading={false}
              error={null}
              state={STATE}
              onStateChange={vi.fn()}
              chip="all"
              onChip={onChip}
              counts={{ all: 2, blocks_billing: 1, human_tasks: 1 }}
              onResolve={onResolve}
              onReopen={onReopen}
              runbooksTo={tenantPathFrom(TENANT, "runbooks")}
              onRunACheck={vi.fn()}
              toHref={(path) => tenantPathFrom(TENANT, path)}
              today={TODAY}
              {...props}
            />
          }
        />
      </Routes>
    </MemoryRouter>,
  );
  return { onResolve, onReopen, onChip };
}

describe("RBS-007 · the work list", () => {
  it("draws the sheet's page head and its six columns in that order", () => {
    draw();
    expect(screen.getByRole("heading", { name: "Work list" })).not.toBeNull();
    expect(screen.getByText("Everything waiting on a person.")).not.toBeNull();
    const headers = screen.getAllByRole("columnheader").map((cell) => cell.textContent?.trim());
    expect(headers.slice(0, 6)).toEqual([
      "What needs doing",
      "From",
      "Weight",
      "Owner",
      "Age",
      "Actions",
    ]);
  });

  it("shows the age as the FIRST sighting — thirty sweeps are one item, thirty days old", () => {
    draw();
    // The 30-day-old row reads `30 days`; the one raised this morning reads
    // `Today`. A cell drawn from `updated_at` would read `Today` for both.
    const ages = screen.getAllByText(/^(Today|\d+ days?)$/).map((n) => n.textContent);
    expect(ages).toEqual(["30 days", "Today"]);
  });

  it("opens the run that raised the item, at the TENANT's address", () => {
    draw();
    const link = screen.getByRole("link", { name: "Can we bill?" });
    // ⚠ The WHOLE href. A wrongly prefixed one still ends with the route.
    expect(link.getAttribute("href")).toBe(
      "/brazosbend/runbooks/configuration_check/runs/22222222-2222-2222-2222-222222222222",
    );
  });

  it("opens the fix at the TENANT's address, and disables it WITH ITS REASON where there is none", () => {
    draw();
    const fixes = screen.getAllByRole("link", { name: "Open the fix" });
    expect(fixes[0].getAttribute("href")).toBe("/brazosbend/settings/tax");
    // The human task carries no route, so the control is DISABLED with its
    // reason rather than hidden (`BR-SHL-025`) — five words (B14 rule 33).
    const disabled = screen.getByRole("button", {
      name: "Open the fix",
    }) as HTMLButtonElement;
    expect(disabled.disabled).toBe(true);
    expect(disabled.getAttribute("title")).toBe("No screen fixes this");
  });

  it("names the weight in words and never as a number a clerk has to decode", () => {
    draw();
    const words = screen
      .getAllByText(/^(Blocks billing|Human task)$/)
      .map((n) => n.textContent);
    expect(words).toContain("Blocks billing");
    expect(words).toContain("Human task");
    // B14 rule 31 — no database id anywhere a reader looks.
    expect(document.body.innerHTML).not.toMatch(/11111111-1111/);
  });

  it("counts the chips from the SERVER's totals, not from the page", () => {
    draw({ rows: [TAX_REGION], total: 2, counts: { all: 900, blocks_billing: 3, human_tasks: 6 } });
    const chips = screen.getByLabelText("Filter the work list");
    expect(within(chips).getAllByRole("button").map((n) => n.textContent)).toEqual([
      "All 900",
      "Blocks billing 3",
      "Cutover 6",
    ]);
  });

  it("resolves an open row and reopens a resolved one", async () => {
    const user = userEvent.setup();
    const { onResolve } = draw();
    await user.click(screen.getAllByRole("button", { name: "Resolve" })[0]);
    expect(onResolve).toHaveBeenCalledWith(TAX_REGION);
    cleanup();

    const { onReopen } = draw({
      rows: [{ ...TAX_REGION, status: "resolved", resolved_at: "2026-09-07T08:00:00Z" }],
      total: 1,
    });
    await user.click(screen.getAllByRole("button", { name: "Reopen" })[0]);
    expect(onReopen).toHaveBeenCalled();
  });

  it("says what is missing and what fills it when nothing is waiting — RBS-007.2", () => {
    draw({ rows: [], total: 0, counts: { all: 0, blocks_billing: 0, human_tasks: 0 } });
    expect(screen.getByText("Nothing waiting")).not.toBeNull();
    expect(screen.getByText("Every check is clear.")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Run a check" })).not.toBeNull();
  });
});

describe("ageWords", () => {
  it("is a function of the day it is HANDED, never of the clock", () => {
    const t = (key: string, options?: Record<string, unknown>) =>
      key === "work.age.today" ? "Today" : `${String(options?.count)} days`;
    expect(ageWords(t, "2026-08-08T09:00:00Z", TODAY)).toBe("30 days");
    expect(ageWords(t, "2026-09-07T06:00:00Z", TODAY)).toBe("Today");
    // A timestamp that will not parse is an em dash, never a friendly guess.
    expect(ageWords(t, "not a date", TODAY)).toBe("—");
  });
});
