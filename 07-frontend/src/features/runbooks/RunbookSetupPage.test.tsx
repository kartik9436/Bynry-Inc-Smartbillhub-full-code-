// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1. `vite.config.ts` keeps
// the default environment at `node` (`DEF-523`); an interactive suite opts in.
/* ══════════════════════════════════════════════════════════════════════════
 * WHAT `RBS-004`'s FOUR COMMIT CONTROLS ACTUALLY DO — AND THE CLOCK ON THE TWO
 * THAT STILL REFUSE.
 *
 * Story: US-RBS-016 · US-RBS-001 — CR-075.
 * Rules: `07-endpoints.md` row 3 (`PUT /runbooks/{key}`) · `BR-RBS-038` (every
 *        edit mints a version) · `BR-RBS-042` (a tenant sets input VALUES) ·
 *        `NFR-5` (no hard caps anywhere) · B14 rules 32 and 33.
 *
 * ⚠ **THIS FILE WAS CITED BY `RunbookSetupPage.tsx` FOR A DAY BEFORE IT
 * EXISTED, AND THAT IS HARD-WON LAW 1 IN ONE LINE.** The page's own header said
 * *"`RunbookSetupPage.test.tsx` asserts that sentence and names the wave that
 * replaces it, so the day `L` lands the test is standing in front of the
 * change"* — and there was no such file. **A comment claiming a guarantee is
 * not the guarantee**, and the guarantee it claimed is the exact one law 2's
 * mirror asks for: a hold with no test that fires when it expires is a promise
 * nobody is keeping. Two of the four holds then landed their routes in wave `E`
 * and went on refusing (`DEF-RBS-4311`), with `tsc`, every gate and 175 runbooks
 * cases green over them — which is `DEF-CWP-3925` again, the defect that left
 * the customer portal with two working doors out of eight.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * HOW A HOLD IS GIVEN A CLOCK HERE, AND WHY IT IS THE EXPORT SURFACE
 * ══════════════════════════════════════════════════════════════════════════
 * Law 2 says to assert a held control's destination BY ADDRESS, so the day the
 * screen lands the suite goes red and names it. `RBS-004`'s remaining hold
 * is not waiting on a SCREEN — it is waiting on an ENDPOINT, and a front-end
 * test cannot see a Django URL table. (It had two; **Change scope** was released
 * in wave `T` and the case that held it is turned around above rather than
 * deleted.)
 *
 * **What it CAN see is the moment somebody writes the client function for that
 * endpoint**, because that is the first thing anyone does. So the last case in
 * this file pins `setupWire.ts`'s export surface: the day a
 * `startRun` or a scope writer appears there, it goes red and its message names
 * the button still saying *"Not connected yet"*. That is a clock a lane trips
 * while doing the very work that expires the hold.
 * ══════════════════════════════════════════════════════════════════════════ */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { matchRoutes, MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import * as setupWire from "./setupWire";
import type { ApiClient, ApiResponse } from "@/api/client";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { APP_ROUTES } from "@/App";

import fixture from "./__fixtures__/rbs004-setup.json";
import { RunbookSetupPage } from "./RunbookSetupPage";
import { RunWizardPage } from "./run/RunWizardPage";

const TENANT = "brazosbend";
const KEY: string = fixture.detail.key;

// No auto-cleanup in this repo (`vite.config.ts` sets no `setupFiles`), so
// every render would otherwise be ADDED to the same document and every count
// here would be wrong. `RunbookSetup.dom.test.tsx` records what that cost.
afterEach(cleanup);

interface Write {
  method: string;
  path: string;
  body: unknown;
}

/** A transport that RECORDS every write instead of performing one.
 *
 *  ⚠ **THE WRITES ARE THE ASSERTION, NOT THE TOAST.** A control that shows a
 *  success message and sends nothing is exactly the shape this file exists to
 *  refuse, and a test that asserted only the message would pass over it. */
function recordingClient(writes: Write[]): ApiClient {
  const answer = <T,>(body: unknown): Promise<ApiResponse<T>> =>
    Promise.resolve({ status: 200, data: body as T, headers: new Headers() } as ApiResponse<T>);

  const get = <T,>(path: string) => {
    if (path === `/runbooks/${KEY}`) return answer<T>(fixture.detail);
    if (path === "/runbooks/runs") return answer<T>(fixture.runs);
    throw new Error(`the screen asked for ${path}, which this fixture does not record`);
  };
  const write =
    (method: string) =>
    <T,>(path: string, body?: unknown) => {
      writes.push({ method, path, body });
      return answer<T>(fixture.detail);
    };

  return {
    request: get,
    get,
    post: write("POST"),
    put: write("PUT"),
    patch: write("PATCH"),
    del: write("DELETE"),
  } as unknown as ApiClient;
}

/** The page at the REAL path pattern (`DEF-CWP-3925`: a bare `MemoryRouter`
 *  gives `useParams()` undefined and every address comes out `//host/…`). */
async function open(hash = "") {
  const writes: Write[] = [];
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const rendered = render(
    <QueryClientProvider client={queryClient}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}/runbooks/${KEY}${hash}`]}>
            <Routes>
              <Route
                path="/:tenant/runbooks/:key"
                element={<RunbookSetupPage client={recordingClient(writes)} />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
  await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeDefined());
  return { ...rendered, writes };
}

describe("RBS-004 · the two holds that EXPIRED, released and asserted by what they do", () => {
  it("Resume writes `enabled` through PUT /runbooks/{key} — the wave E route", async () => {
    // The recorded runbook is paused (`enabled: false`), so the header's
    // secondary action reads **Resume** and its job is to turn it back on.
    expect(fixture.detail.enabled).toBe(false);
    const { writes } = await open();

    fireEvent.click(screen.getByRole("button", { name: "Resume" }));

    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].method).toBe("PUT");
    // ⚠ **BY ADDRESS.** Law 2: assert the destination, never that a string is
    // present. `//host/runbooks/x` reads as a perfectly good path to a
    // `toContain` and reaches another origin entirely.
    expect(writes[0].path).toBe(`/runbooks/${KEY}`);
    expect(writes[0].body).toEqual({ enabled: true });
  });

  it("Change limits writes the cap and the approval, and nothing else", async () => {
    const { writes } = await open("#limits");

    fireEvent.click(screen.getByRole("button", { name: "Change limits" }));
    // The sheet's own two editable rows. `Fees` and `Who can approve` have no
    // field on the wire, so offering an input for them would be a control that
    // discards what a person typed.
    const cap = await screen.findByLabelText("Most per run");
    fireEvent.change(cap, { target: { value: "250" } });
    fireEvent.click(screen.getByRole("button", { name: "Save limits" }));

    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].method).toBe("PUT");
    expect(writes[0].path).toBe(`/runbooks/${KEY}`);
    expect(writes[0].body).toEqual({ cap: 250, gate_mode: fixture.detail.gate_mode });
  });

  it("an empty cap clears it rather than sending zero — NFR-5 has no hard caps", async () => {
    const { writes } = await open("#limits");
    fireEvent.click(screen.getByRole("button", { name: "Change limits" }));
    fireEvent.change(await screen.findByLabelText("Most per run"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save limits" }));

    await waitFor(() => expect(writes).toHaveLength(1));
    // `null` and not `0`: *no cap* must stay expressible, and a zero cap would
    // mean a runbook that may act on nothing.
    expect((writes[0].body as { cap: number | null }).cap).toBeNull();
  });
});

describe("RBS-004 · the hold that EXPIRED, and the one that is still true", () => {
  /**
   * ⚠ **THE RUN HOLD EXPIRED ON 2026-10-07 (`CR-173-BRC10`) AND THIS CASE IS IT,
   * TURNED AROUND.** It asserted that **Run ▶** wrote nothing and said *Not
   * connected yet.*; `POST /runbooks/{key}/runs` landed, `startRun` joined
   * `setupWire.ts`, and the export-surface case below went red naming it —
   * exactly as written. What it asserts now: the button opens a dialog, and its
   * submit WRITES, by ADDRESS, a dry run by default.
   */
  /** `CR-173-BRC10` — PO 2026-10-07 Q6, *"User will configure this in runbook on
   *  thier own"*: the time is the UTILITY's, written as a daily cron in its zone. */
  it("Change schedule writes a daily time on the utility's clock", async () => {
    const { writes } = await open();
    fireEvent.click(screen.getByRole("button", { name: "Change schedule" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Runs"), { target: { value: "schedule" } });
    fireEvent.change(await within(dialog).findByLabelText("Time"), { target: { value: "21:30" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save schedule" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].method).toBe("PUT");
    expect(writes[0].path).toBe(`/runbooks/${KEY}`);
    expect(writes[0].body).toEqual({
      trigger_kind: "schedule",
      cron: "30 21 * * *",
      timezone: "America/Chicago",
    });
  });

  /**
   * ⚠ **TURNED AROUND A SECOND TIME, 2026-10-13 (`OQ-WRK-12792` → A,
   * `DEF-WRK-10123`).** This case asserted that **Run ▶** opened a small dialog
   * whose submit POSTed a dry run. The PO chose the full-screen Check wizard
   * over the pop-up, and the pop-up was deleted in the same change — so what
   * it asserts now is that **Run ▶** is a LINK to the wizard's address, that
   * following it lands on the wizard under the real route pattern, and that
   * NOTHING is written by the setup page any more. The POST is the wizard's,
   * and `run/RunWizardPage.dom.test.tsx` asserts it by address.
   */
  it("Run ▶ opens the Check wizard at /{tenant}/runbooks/{key}/run — no pop-up, no write here", async () => {
    const writes: Write[] = [];
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
          <ToastProvider>
            <MemoryRouter initialEntries={[`/${TENANT}/runbooks/${KEY}`]}>
              <Routes>
                <Route
                  path="/:tenant/runbooks/:key"
                  element={<RunbookSetupPage client={recordingClient(writes)} />}
                />
                <Route
                  path="/:tenant/runbooks/:key/run"
                  element={<RunWizardPage client={recordingClient(writes)} />}
                />
              </Routes>
            </MemoryRouter>
          </ToastProvider>
        </TenantRegionalProvider>
      </QueryClientProvider>,
    );
    const run = await screen.findByRole("link", { name: "Run ▶" });
    // BY ADDRESS, built from the tenant — never `//host/…` (`DEF-CWP-3925`).
    expect(run.getAttribute("href")).toBe(`/${TENANT}/runbooks/${KEY}/run`);
    // …and the REAL route table opens it with its own pattern, not `:key`'s.
    const matched = matchRoutes(APP_ROUTES, `/${TENANT}/runbooks/${KEY}/run`) ?? [];
    expect(matched[matched.length - 1]?.route?.path).toBe("runbooks/:key/run");

    fireEvent.click(run);
    await waitFor(() =>
      expect(document.querySelector('[data-screen="RBS-005"]')).not.toBeNull(),
    );
    expect(document.querySelector('[data-run-phase="scoping"]')).not.toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(writes).toEqual([]);
  });

  /**
   * ⚠ **THIS CASE IS THE HOLD, TURNED AROUND RATHER THAN DELETED.** It asserted
   * that **Change scope** wrote NOTHING, and it was true: `EDITABLE_SETTINGS`
   * held eight schedule-and-limit fields and no parameter value, so there was
   * nowhere to save one (`DEF-RBS-4338`). Wave `T` added `runbooks.parameters`,
   * the domain route and the ninth editable setting, and the export-surface case
   * below went RED naming this button on the commit that added
   * `listParameterDomain` — a lane tripping the clock while doing the very work
   * that expires the hold. What it asserts now is the mirror of what it
   * asserted then: the button WRITES, by ADDRESS, and the whole document goes.
   */
  it("Change scope now writes the inputs through PUT /runbooks/{key}", async () => {
    const { writes } = await open("#scope");
    fireEvent.click(screen.getByRole("button", { name: "Change scope" }));

    // The sheet draws one control per declared input. `Report` is an enum over
    // the runbook's OWN vocabulary, so it is a select and its options are
    // de-cased — a raw `blockers_and_warnings` in front of a clerk is B14
    // rule 32 (`DEF-RBS-4339`).
    const report = await screen.findByLabelText("Report");
    fireEvent.change(report, { target: { value: "blockers_only" } });
    fireEvent.click(screen.getByRole("button", { name: "Save scope" }));

    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].method).toBe("PUT");
    // ⚠ **BY ADDRESS.** `//host/runbooks/x` reads as a perfectly good path to a
    // `toContain` and reaches another origin entirely (`DEF-CWP-3925`).
    expect(writes[0].path).toBe(`/runbooks/${KEY}`);
    const body = writes[0].body as { parameters: Record<string, unknown> };
    expect(body.parameters.report).toBe("blockers_only");
    // The WHOLE document, never a delta: a delta cannot say *put this input
    // back to what it shipped with*.
    expect(Object.keys(body.parameters).sort()).toEqual([
      "include_held_accounts",
      "raise_work_items",
      "report",
      "usage_to_cover",
    ]);
    // …and nothing but `parameters` travels, so a scope save cannot move a cap.
    expect(Object.keys(writes[0].body as object)).toEqual(["parameters"]);
  });

  /**
   * ⚠ **THE CLOCK. THIS CASE IS THE WHOLE REASON THE FILE EXISTS.**
   *
   * `Run ▶` waits on `POST /runbooks/{key}/runs` (task `L`, phase 2) and
   * `Change scope` waits on a route that stores a `Parameter` VALUE —
   * `services.EDITABLE_SETTINGS` is eight settings and a scope row is not one
   * of them, so `BR-RBS-042`'s *a tenant sets input values* has nowhere to put
   * one today. Neither hold can be checked against a Django URL table from
   * here.
   *
   * **What CAN be checked is the first thing anybody does when they build
   * either route: they add a function to `setupWire.ts`.** So this
   * pins that module's export surface. The day a run-starter or a scope writer
   * appears, this goes red and names the button that is still refusing over it
   * — which is a lane tripping the clock while doing the very work that expires
   * the hold, rather than a promise nobody is keeping.
   *
   * ⚠ **AND IT IS A SET COMPARISON, NOT A COUNT.** A count would pass over a
   * rename and fail over an unrelated addition; the set says which name
   * arrived, in the failure message, which is what a reader needs at 2am.
   */
  it("goes RED the day a run-starter joins the client", () => {
    expect(new Set(Object.keys(setupWire))).toEqual(
      new Set([
        "getRunbookDetail",
        "editRunbook",
        "cloneRunbook",
        "listRunsForRunbook",
        // ⚠ **THE SCOPE WRITER ARRIVED AND THIS CASE IS WHAT SAID SO.** Adding
        // `listParameterDomain` in wave `T` turned this red, naming
        // **Change scope**, before a line of the modal existed — which is the
        // whole point of pinning a surface rather than counting one. It stays,
        // one name shorter in what it is still waiting for: `Run ▶` waits on
        // `POST /runbooks/{key}/runs`, and the first thing anybody building it
        // does is add a function here.
        "listParameterDomain",
        // ⚠ AND THE RUN-STARTER ARRIVED (`CR-173-BRC10`, 2026-10-07) — this case
        // went red naming it, and **Run ▶** stopped refusing in the same commit.
        "startRun",
      ]),
    );
  });
});
