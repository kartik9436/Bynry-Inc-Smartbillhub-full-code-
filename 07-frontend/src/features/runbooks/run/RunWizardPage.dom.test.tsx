// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1 (`DEF-523`).
/* ══════════════════════════════════════════════════════════════════════════
 * THE CHECK WIZARD AT ITS ADDRESS — THE ONE WAY A RUN STARTS.
 *
 * `OQ-WRK-12792` → A (PO 2026-10-13, *"1a, 2A 3A"*) · `DEF-WRK-10123`: the
 * wizard was built and never routed, and a run started from a small pop-up.
 *
 * Every case mounts the page under the REAL path pattern — `APP_ROUTES`
 * itself is asked which pattern serves the address, and the page is then
 * mounted at that pattern beside RBS-006's own, so a run that finishes is
 * proved to LAND on its result by address (`DEF-CWP-3925`: a bare
 * `MemoryRouter` builds `//host/…` and `toContain` cannot tell).
 *
 * The client RECORDS writes: the POST is the assertion, never a toast.
 * ══════════════════════════════════════════════════════════════════════════ */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { matchRoutes, MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import type { ApiClient, ApiResponse } from "@/api/client";
import { ApiError } from "@/api/client";
import { resolveScreen } from "@/routing/screenIds";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import fixture from "../__fixtures__/rbs004-setup.json";
import { RunWizardPage, runIdFromResultLink } from "./RunWizardPage";

afterEach(cleanup);

const TENANT = "brazosbend";
const KEY: string = fixture.detail.key;
const RUN_ID = "7f1c2a90-0000-4000-8000-000000000001";

interface Write {
  method: string;
  path: string;
  body: unknown;
}

type JobEnd = "succeeded" | "failed";

/** The NEW WORLD push's shape: an Action with a one-off *Day* input. */
const ACTION = {
  ...fixture.detail,
  kind: "action",
  parameters: [
    ...fixture.detail.parameters,
    {
      name: "day",
      label: "Day",
      type: "text",
      required: false,
      domain: null,
      multi: false,
      choices: [],
      setting_key: null,
      value: null,
      is_set: false,
      value_labels: {},
    },
  ],
};

/** `DEF-WRK-10124` — the utility has not added this runbook: the server's 404. */
const NOT_ADDED = Symbol("not-added");

function client(writes: Write[], end: JobEnd, detail: unknown = fixture.detail): ApiClient {
  const answer = <T,>(body: unknown, status = 200): Promise<ApiResponse<T>> =>
    Promise.resolve({ status, data: body as T, headers: new Headers() } as ApiResponse<T>);
  const get = <T,>(path: string) => {
    if (path === `/runbooks/${KEY}`) {
      if (detail === NOT_ADDED) return Promise.reject(new ApiError(404, { code: null, message_key: "errors.not_found" }));
      return answer<T>(detail);
    }
    if (path === "/jobs/job-1") {
      return answer<T>({
        id: "job-1",
        kind: "runbooks.check",
        status: end,
        progress: null,
        result_link: end === "succeeded" ? `/api/runbooks/runs/${RUN_ID}` : null,
        error: end === "failed" ? "boom" : null,
      });
    }
    throw new Error(`the screen asked for ${path}, which this fixture does not record`);
  };
  const post = <T,>(path: string, body?: unknown) => {
    writes.push({ method: "POST", path, body });
    return answer<T>({ job_id: "job-1", status_url: "/api/jobs/job-1" }, 202);
  };
  const refuse = () => {
    throw new Error("the wizard wrote something other than a run");
  };
  return { request: get, get, post, put: refuse, patch: refuse, del: refuse } as unknown as ApiClient;
}

function Landed() {
  const { runId } = useParams();
  return <div data-landed={runId} />;
}

async function openWizard(end: JobEnd, detail: unknown = fixture.detail) {
  const writes: Write[] = [];
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}/runbooks/${KEY}/run`]}>
            <Routes>
              <Route
                path="/:tenant/runbooks/:key/run"
                element={
                  <RunWizardPage
                    client={client(writes, end, detail)}
                    poll={{ sleep: () => Promise.resolve(), intervalMs: 0 }}
                  />
                }
              />
              <Route path="/:tenant/runbooks/:key/runs/:runId" element={<Landed />} />
              <Route path="/:tenant/runbooks/:key" element={<div data-landed="setup" />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
  await waitFor(() => expect(document.querySelector('[data-screen="RBS-005"]')).not.toBeNull());
  return { writes };
}

describe("RBS-004.run — the address", () => {
  it("the real route table serves /{tenant}/runbooks/{key}/run with the wizard's own pattern", () => {
    const matched = matchRoutes(APP_ROUTES, `/${TENANT}/runbooks/${KEY}/run`) ?? [];
    // Not `runbooks/:key` (the setup screen for a runbook keyed `run`) and not
    // the catch-all — the wizard's own row.
    expect(matched[matched.length - 1]?.route?.path).toBe("runbooks/:key/run");
  });

  it("the badge is a dotted sub-id of the runbook screen, never an invented A1 number", () => {
    const screenId = resolveScreen(`/${TENANT}/runbooks/${KEY}/run`);
    expect(screenId.r10).toBe("RBS-004.run");
    expect(screenId.a1).toBeNull();
  });
});

describe("RBS-004.run — Scope", () => {
  it("opens on Scope with the runbook's inputs, and draws no Matches count it does not have", async () => {
    await openWizard("succeeded");
    expect(document.querySelector('[data-run-phase="scoping"]')).not.toBeNull();
    expect(document.querySelector('[data-run-input="report"]')?.textContent).toContain("Report");
    // Nothing serves resolve(params)'s count, so the row is not drawn.
    expect(document.querySelector('[data-run-input="matches"]')).toBeNull();
    expect(screen.getByRole("button", { name: "Run this check →" })).toBeTruthy();
    // No dead buttons: no draft to save, no stop route, no support destination.
    expect(document.querySelector('[data-run-action="draft"]')).toBeNull();
    expect(document.querySelector('[data-run-action="stop"]')).toBeNull();
    // A Check offers no "Run for real".
    expect(document.querySelector("#run_mode")).toBeNull();
  });

  it("Cancel goes back to the runbook, by address", async () => {
    await openWizard("succeeded");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(document.querySelector('[data-landed="setup"]')).not.toBeNull());
  });
});

describe("DEF-WRK-10124 — a runbook not added yet", () => {
  it("offers the template's own page instead of a load failure", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
          <ToastProvider>
            <MemoryRouter initialEntries={[`/${TENANT}/runbooks/${KEY}/run`]}>
              <Routes>
                <Route
                  path="/:tenant/runbooks/:key/run"
                  element={<RunWizardPage client={client([], "succeeded", NOT_ADDED)} />}
                />
                <Route path="/:tenant/runbooks/templates/:key" element={<div data-landed="template" />} />
              </Routes>
            </MemoryRouter>
          </ToastProvider>
        </TenantRegionalProvider>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(document.querySelector('[data-run-wizard="not-added"]')).not.toBeNull());
    expect(screen.getByText("Not added yet.")).toBeTruthy();
    fireEvent.click(screen.getByRole("link", { name: "+ Add from templates" }));
    await waitFor(() => expect(document.querySelector('[data-landed="template"]')).not.toBeNull());
  });
});

describe("RBS-004.run — Start → Checking → the run's result", () => {
  it("POSTs a dry run to /runbooks/{key}/runs, polls the job, and LANDS on the run's result", async () => {
    const { writes } = await openWizard("succeeded");
    fireEvent.click(screen.getByRole("button", { name: "Run this check →" }));
    await waitFor(() => expect(document.querySelector(`[data-landed="${RUN_ID}"]`)).not.toBeNull());
    expect(writes).toHaveLength(1);
    expect(writes[0].method).toBe("POST");
    expect(writes[0].path).toBe(`/runbooks/${KEY}/runs`);
    expect(writes[0].body).toEqual({ mode: "dry", parameters: {} });
  });

  it("a job that FAILS is the wizard's failed state, with Try again — and no Tell support", async () => {
    const { writes } = await openWizard("failed");
    fireEvent.click(screen.getByRole("button", { name: "Run this check →" }));
    await waitFor(() =>
      expect(document.querySelector('[data-run-phase="checkFailed"]')).not.toBeNull(),
    );
    expect(screen.getByText("A check could not finish.")).toBeTruthy();
    // Every declared step is listed, and an unreached one says so (RBR-01).
    const steps = document.querySelectorAll("[data-run-progress-step]");
    expect(steps.length).toBe(fixture.detail.definition.steps.length);
    expect(steps[0]?.textContent).toContain("The run did not get this far.");
    expect(screen.getByRole("button", { name: "Try again ▶" })).toBeTruthy();
    expect(document.querySelector('[data-run-action="tell-support"]')).toBeNull();
    // Try again starts a SECOND run, by the same address.
    fireEvent.click(screen.getByRole("button", { name: "Try again ▶" }));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[1].path).toBe(`/runbooks/${KEY}/runs`);
  });
});

describe("RBS-004.run — an Action keeps the two questions the pop-up asked", () => {
  it("asks How to run and the one-off Day; Run for real is the danger tier and says so", async () => {
    const { writes } = await openWizard("succeeded", ACTION);
    const how = document.querySelector<HTMLSelectElement>("#run_mode");
    expect(how).not.toBeNull();
    fireEvent.change(how as HTMLSelectElement, { target: { value: "live" } });
    fireEvent.change(screen.getByLabelText("Day"), { target: { value: "2026-10-12" } });
    const start = await screen.findByRole("button", { name: "Run for real ▶" });
    expect(start.getAttribute("data-variant")).toBe("danger");
    expect(screen.getByText("This run acts for real.")).toBeTruthy();
    expect(screen.queryByText("This check changes nothing.")).toBeNull();
    fireEvent.click(start);
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].body).toEqual({ mode: "live", parameters: { day: "2026-10-12" } });
  });
});

describe("runIdFromResultLink", () => {
  it("reads the run id the job body writes, and nothing else", () => {
    expect(runIdFromResultLink(`/api/runbooks/runs/${RUN_ID}`)).toBe(RUN_ID);
    expect(runIdFromResultLink(null)).toBeNull();
    expect(runIdFromResultLink("/api/exports/abc")).toBeNull();
  });
});

/* ── Lifecycle ─────────────────────────────────────────────
 * packet: OQ-WRK-12792 → A (PO 2026-10-13) · DEF-WRK-10123
 * generated: 2026-10-13 by the runbook-wizard + settings-field lane
 * gates: ./node_modules/.bin/vitest run src/features/runbooks/run/RunWizardPage.dom.test.tsx — RED before the route and the page existed (no runbooks/:key/run pattern; the module did not resolve), GREEN after
 * status: VERIFIED-UNRATIFIED
 * ────────────────────────────────────────────────────────── */
