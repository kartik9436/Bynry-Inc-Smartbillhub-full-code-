// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-MET-4761 — two ways to take a unit out of service, and the one
//          on the list row recorded neither the date nor the reason ·
//          DEF-MET-4731 — two edit forms for one unit, the units list keeping a
//          private copy the unit's own page does not use.
// Change:  CR-089 · the `U10` and `U12` conformance pass. PO ruling 2026-09-10
//          on the premises twin (`DEF-4743`), option (b): keep the shortcut,
//          point it at the real dialog.
// Rules:   BR-MET-1164 (a unit is held by an open account, and the refusal
//          NAMES it) · BR-MET-035 (a status change is the System Admin's) ·
//          B14 rule 6 (danger tier) · B14 rule 37 (a drawn figure is an
//          illustration, never a fact to build to)
// Screens: S15 · PRM-01U the units list · U10 · U12
// ───────────────────────────────────────────────────────
// **THE GUARD THIS FILE EXISTS TO BE, IN ONE SENTENCE: A SECOND DOOR CANNOT
// COME BACK WITHOUT A RED LINE.**
//
// Both defects are the same shape and neither was visible to anything the repo
// already had. Two forms that write one endpoint both typecheck, both pass
// their own tests, and neither knows the other exists. Two doors out of service
// both enforced `BR-MET-1164` — off the same computation, so nothing unsafe got
// through either — and differed ONLY in what reached `audit_log`, which no
// check in this repo reads.
//
// ⚠ **SO THE ASSERTIONS ARE ABOUT THE ABSENCE OF A SECOND PATH, NOT ABOUT THE
// FIRST ONE WORKING.** A test that opens the dialog and drives it green would
// have passed on both defects: the good dialog was already there and already
// worked. What separates the fixed product from the broken one is that
// `POST /units/{id}/deactivate` is never reached from a screen, and that the
// pencil and the unit page's ✎ resolve to ONE component.
//
// ⚠ **PROVED RED FIRST (hard-won law 7), through `vitest run`, which is the
// harness that will run it.** Against the pre-fix file:
//   · *the row action opens the dialog that demands a date and a reason* fails
//     on `Unable to find an element with the text: Not while this is live` —
//     the plain confirm has no refusal panel at all;
//   · *no screen posts the door that records nothing* fails on
//     `expected [ 'features/metering/UnitsListPage.tsx' ] to have length 0`;
//   · *one edit form* fails on
//     `expected 2 to be 1` — two `function UnitEditModal` declarations.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { MyPermissions, StatusChangeView, UnitRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { PREMISES_PERMISSION } from "./meteringShared";
import { UnitsListPage } from "./UnitsListPage";

// Node's own modules, reached the way `styles/routeBUtilities.test.ts` does —
// the string-split import keeps Vite from trying to pre-bundle them.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  readdirSync(p: string, o: { withFileTypes: true }): { name: string; isDirectory(): boolean }[];
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
  dirname(p: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(u: string): string;
};

const TENANT = "brazosbend";
// ⚠ **RESOLVED FROM THIS FILE, NOT FROM `process.cwd()`.** The working
// directory a runner happens to start in is not a fact about the tree, and
// `process` is not typed here at all — `styles/routeBUtilities.test.ts` walks up
// from `import.meta.url` for the same reason.
const SRC = nodePath.dirname(
  nodePath.dirname(nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url))),
);
/** This file names both patterns it sweeps for, in its own prose and in its own
 *  regexes, so it must exclude itself or it is its own only offender. */
const SELF = "UnitsListOneDoor.dom.test.tsx";

/** Every `.ts`/`.tsx` file under `src/`, so the sweep below cannot miss a
 *  screen by being pointed at one directory. */
function everySourceFile(dir: string, out: string[] = []): string[] {
  for (const entry of nodeFs.readdirSync(dir, { withFileTypes: true })) {
    const full = nodePath.join(dir, entry.name);
    if (entry.isDirectory()) {
      everySourceFile(full, out);
    } else if (/\.tsx?$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

function unit(over: Partial<UnitRow> = {}): UnitRow {
  return {
    id: "u-501",
    unit_no: "U-00501",
    premises_id: "p-101",
    premise_no: "P-00101",
    premise_address: "1408 Bluestem Ln",
    label: "2",
    unit_type: "residential",
    floor_label: "Ground",
    square_feet: 820,
    rate_plan_id: null,
    plan_effective_from: null,
    plan_locked: false,
    vacant_standby_auto: false,
    is_common_area: false,
    services: ["electric", "water"],
    lat: null,
    lng: null,
    point: { lat: "30.752104", lng: "-98.238391", source: "premises" },
    active: true,
    metered_services: [],
    meters: [],
    occupancy: "occupied",
    occupant: "Dana Whitfield",
    account_no: "A-90001",
    status: "active",
    sub_metered: false,
    ...over,
  };
}

/** The unit's live dependencies as `GET /units/{id}/status-change` serves them.
 *  ⚠ The account number is the FIXTURE's, not the blueprint's — B14 rule 37. */
function blockedView(): StatusChangeView {
  return {
    entity: "unit",
    id: "u-501",
    status: "active",
    target_status: "inactive",
    blocked: true,
    held_by: "open_accounts",
    dependencies: [
      {
        kind: "open_accounts",
        count: 1,
        blocking: true,
        reference: "A-90001",
        link: { route: "unit_account", unit_id: "u-501" },
      },
      {
        kind: "attached_assets",
        count: 2,
        blocking: false,
        link: { route: "unit_assets", unit_id: "u-501" },
      },
    ],
  };
}

interface Call {
  url: string;
  method: string;
}

/** BR-SHL-025: the row actions are drawn ENABLED only for a role the server
 *  says may write, so a fixture with no permissions renders the guarded
 *  variant and the door under test is never reachable. */
function fullAccess(): MyPermissions {
  return {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  };
}

function mountList(calls: Call[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, fullAccess());
  const fetchImpl = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, method: String(init?.method ?? "GET").toUpperCase() });
    // `/settings/services` answers a bare ARRAY and everything else a page —
    // a mock that returns one shape for both crashes the screen inside React
    // with `Cannot read properties of undefined`, which reads like a component
    // bug and is a fixture bug.
    const body = url.includes("/status-change")
      ? blockedView()
      : url.includes("/settings/services")
        ? []
        : url.includes("/permissions")
          ? fullAccess()
          : url.includes("/units")
            ? { results: [unit()], count: 1 }
            : { results: [], count: 0 };
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  const client = createApiClient({ tenant: TENANT, fetchImpl });
  // ⚠ MOUNTED UNDER THE REAL PATH PATTERN (hard-won law 2). A bare
  // `MemoryRouter` leaves `useParams().tenant` undefined and every link the
  // dialog builds comes out `//premises/…` — a perfectly good string to
  // `toContain` and a URL to another host.
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/premises/units`]}>
          <Routes>
            <Route
              path="/:tenant/premises/units"
              element={
                <UnitsListPage
                  client={client}
                  timeZone="America/Chicago"
                  dateFormat="MM/DD/YYYY"
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("DEF-MET-4761 — one door out of service, and it records what it did", () => {
  it("the row action opens the dialog that demands a date and a reason", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    mountList(calls);

    await screen.findByText("1408 Bluestem Ln");
    await user.click(await screen.findByRole("button", { name: "Deactivate" }));

    // The drawn refusal panel — the thing the plain confirm did not have.
    expect(await screen.findByText("Not while this is live")).toBeInTheDocument();
    expect(screen.getByText("Account A-90001 is still open")).toBeInTheDocument();
    // The three drawn inputs, all required, none of which the old door asked.
    expect(screen.getByLabelText(/New status/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^From/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Why/)).toBeInTheDocument();
    // B14 rule 6, and the drawn commit label, held by the open account.
    const commit = screen.getByRole("button", { name: "Deactivate unit" });
    expect(commit).toHaveAttribute("data-variant", "danger");
    expect(commit).toBeDisabled();
  });

  it("pressing through the held dialog posts NOTHING at all", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    mountList(calls);

    await screen.findByText("1408 Bluestem Ln");
    await user.click(await screen.findByRole("button", { name: "Deactivate" }));
    await screen.findByText("Not while this is live");
    await user.click(screen.getByRole("button", { name: "Deactivate unit" }));

    await waitFor(() => expect(screen.getByText("Close the account first")).toBeInTheDocument());
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);
  });

  it("no screen anywhere posts the door that records nothing", () => {
    // ⚠ **THE SWEEP IS THE GUARD, NOT THE TWO CASES ABOVE.** Those prove the
    // door that exists behaves; this proves no OTHER one appeared. It reads
    // every file under `src/` rather than the units list alone, because the
    // defect was never that one file was wrong — it was that two files did the
    // same job and nothing compared them.
    const offenders = everySourceFile(SRC)
      .filter((path) => !path.endsWith(nodePath.join("src", "api", "endpoints.ts")))
      .filter((path) => !path.endsWith(SELF))
      .filter((path) => {
        const text = nodeFs.readFileSync(path, "utf8");
        return /deactivateUnit\s*\(/.test(text) || /units\/\$\{[^}]+\}\/deactivate/.test(text);
      })
      .map((path) => path.slice(SRC.length + 1));
    expect(offenders).toEqual([]);
  });
});

describe("DEF-MET-4731 — one edit form for a unit, reached from both doors", () => {
  it("the product declares exactly one UnitEditModal", () => {
    const declarations = everySourceFile(SRC)
      .filter((path) => !path.endsWith(SELF))
      .filter((path) =>
        /(export )?function UnitEditModal\b/.test(nodeFs.readFileSync(path, "utf8")),
      );
    expect(declarations.map((path) => path.slice(SRC.length + 1))).toEqual([
      nodePath.join("features", "metering", "UnitEditModal.tsx"),
    ]);
  });

  it("the units list and the unit's page import the SAME form", () => {
    // ⚠ **THE NAMED-IMPORT LIST MAY GROW, AND PINNING IT EXACTLY BROKE THIS
    // ONCE.** `UnitsListPage` later imported `unitFormTitle` from the same
    // module and a regex demanding `{ UnitEditModal }` alone went red on a
    // change that was not about doors at all. What this case is FOR is that
    // both files import the component from ONE module.
    const imports = (file: string) =>
      /import\s*\{[^}]*\bUnitEditModal\b[^}]*\}\s*from\s*"\.\/UnitEditModal"/.test(
        nodeFs.readFileSync(nodePath.join(SRC, "features", "metering", file), "utf8"),
      );
    expect(imports("UnitsListPage.tsx")).toBe(true);
    expect(imports("UnitDetailPage.tsx")).toBe(true);
  });
});
