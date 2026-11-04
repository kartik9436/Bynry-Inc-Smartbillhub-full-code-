// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LINE 1 AND THE FILE IS `.dom.test.tsx` — `vitest.config.ts`'s
// convention (DEF-523): the default environment is `node`, and an interactive
// suite opts in per file.
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    CR-142-BRC07 Phase 4 · `P4.15` · Screen: CWP-078
// Rules:    **R24c LAW (ruled)** — *"In the customer portal a landlord sees
//           their own master account only: the $69.60, never Unit 3's
//           $100.00"* · BR-CWP-016 · BR-CWP-015 (never merged; nothing beside
//           the total to press) · BR-CWP-093 (nothing empty ever appears) ·
//           CLAUDE.md hard rule 2 (stored 4 dp, DISPLAY 2) · hard rule 8 ·
//           B14 rule 20 · rule 31 (no database id is a visible value) ·
//           rule 33 (RATIONALE is zero words on screen)
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PremisesStatement } from "../api/portalClient";

let read: () => Promise<PremisesStatement> = async () => {
  throw new Error("no behaviour set");
};
// A plain function reference rather than `vi.fn()` — `MyAccounts.dom.test.tsx`
// records why: the spy's settled-result tracking attaches to a rejected promise
// before the component's own `.catch` and reports a handled error as a failure.
const asked: string[] = [];
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getPremisesStatement: (accountId: string) => {
      asked.push(accountId);
      return read();
    },
  };
});

const { PremisesStatementView } = await import("./PremisesStatement");

const MASTER_ID = "01999999-0000-7000-8000-0000000master".replace(/[^0-9a-f-]/g, "0");
const UNIT_ID = "01999999-0000-7000-8000-00000000unit".replace(/[^0-9a-f-]/g, "0");

/** The landlord's view of 1408 Elm Street — `R24c`'s own figures, scoped.
 *
 *  ⚠ **ONE ROW, NOT FIVE.** The staff report draws five accounts at this
 *  address; the server sends the owner ONE, and the fixture says one because
 *  that is what the endpoint answers. A fixture holding five and a screen
 *  hiding four would be testing the wrong thing entirely. */
const LANDLORD: PremisesStatement = {
  from: "2026-09-01",
  to: "2026-09-30",
  address: "1408 Elm Street",
  count: 1,
  page: 1,
  per: 50,
  account_count: 1,
  totals: { charges: "69.6000", credits: "0.0000", closing: "69.6000" },
  common_areas: "69.6000",
  rows: [
    {
      id: MASTER_ID,
      account_no: "100900",
      unit_label: null,
      is_master: true,
      holding: "holder",
      opening: "0.0000",
      charges: "69.6000",
      credits: "0.0000",
      closing: "69.6000",
    },
  ],
};

/** The TENANT at Unit 3 — `$100.00`, and no common-area tile at all. */
const TENANT: PremisesStatement = {
  from: "2026-09-01",
  to: "2026-09-30",
  address: "1408 Elm Street",
  count: 1,
  page: 1,
  per: 50,
  account_count: 1,
  totals: { charges: "196.0000", credits: "96.0000", closing: "100.0000" },
  common_areas: null,
  rows: [
    {
      id: UNIT_ID,
      account_no: "100903",
      unit_label: "Unit 3",
      is_master: false,
      holding: "holder",
      opening: "0.0000",
      charges: "196.0000",
      credits: "96.0000",
      closing: "100.0000",
    },
  ],
};

/** ⚠ **MOUNTED UNDER THE REAL PATH PATTERN**, which is hard-won law 2's own
 *  fixture clause: a component mounted bare in a `MemoryRouter` with no
 *  `/:tenant/portal` route leaves `useParams().tenant` undefined, and every
 *  address it builds comes out `//portal/…` — a protocol-relative URL to
 *  another host that reads as a perfectly good string to `toContain`. */
function mount(accountId: string) {
  return render(
    <MemoryRouter initialEntries={["/brazosbend/portal/property"]}>
      <Routes>
        <Route
          path="/:tenant/portal/property"
          element={
            <PremisesStatementView accountId={accountId} from="2026-09-01" to="2026-09-30" />
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  asked.length = 0;
});

describe("CWP-078 — the property statement is scoped to what you hold", () => {
  it("shows the owner their $69.60 and Unit 3's $100.00 nowhere on the page", async () => {
    read = async () => LANDLORD;
    mount(MASTER_ID);

    expect(await screen.findByText("1408 Elm Street")).toBeInTheDocument();
    // Hard rule 2 — stored at four decimals, DISPLAYED at two.
    expect(await screen.findAllByText("$69.60")).not.toHaveLength(0);

    // ⚠ **THE ABSENCE IS ASSERTED OVER THE WHOLE RENDERED PAGE**, not over one
    // cell. `queryByText("$100.00")` on a column somebody remembered to name
    // would pass over a total, a tile or a `title` carrying the same figure —
    // which is exactly how a scoped screen leaks.
    expect(document.body.textContent).not.toContain("$100.00");
    expect(document.body.textContent).not.toContain("196");
  });

  it("shows a tenant their own $100.00 and no common-area tile", async () => {
    read = async () => TENANT;
    mount(UNIT_ID);

    expect(await screen.findAllByText("$100.00")).not.toHaveLength(0);
    // `BR-CWP-093` — ABSENT, never `$0.00`. A zero here would be a claim about
    // what the building's common areas cost, read by somebody it is not about.
    expect(screen.queryByTestId).toBeDefined();
    expect(document.querySelector('[data-tile="tile-common"]')).toBeNull();
    expect(document.body.textContent).not.toContain("$69.60");
  });

  it("puts no database id on the page (B14 rule 31)", async () => {
    read = async () => LANDLORD;
    mount(MASTER_ID);
    await screen.findByText("1408 Elm Street");

    // The id is the SUBJECT of the read and must never be a visible value.
    expect(document.body.textContent).not.toContain(MASTER_ID);
    // …and it IS what the screen asked the server for, which is the half that
    // proves the absence above is not simply a screen that fetched nothing.
    expect(asked).toEqual([MASTER_ID]);
  });

  it("says nothing on screen about why a neighbour's balance is absent", async () => {
    // B14 rule 33 — RATIONALE is ZERO WORDS on screen. The honest build is
    // silence: the page never explains the scoping and never claims anything
    // about what it is not showing.
    read = async () => LANDLORD;
    mount(MASTER_ID);
    await screen.findByText("1408 Elm Street");

    const text = (document.body.textContent ?? "").toLowerCase();
    for (const forbidden of ["tenant", "privacy", "not shown", "only your", "hidden"]) {
      expect(text).not.toContain(forbidden);
    }
  });
});
