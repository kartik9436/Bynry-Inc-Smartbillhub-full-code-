// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1 (`DEF-523`).
// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-016 · US-RBS-001 (EP-RBS-01) — CR-075 wave C task C2.
// Screens: RBS-006 (`S152`) at `/{tenant}/runbooks/{key}/runs/{runId}`.
// Rules:   `07-endpoints.md` rows 9 and 10 · `BR-RBS-011` (a failure names its
//          fix route) · `BR-RBS-020` (the report is frozen at close) ·
//          `BR-RBS-035` · `NFR-3` · `BR-SHL-023` (one formatting path).
// Defects: DEF-RBS-4335 (this file was CITED by two others and had never been
//          written) · DEF-RBS-4329 (fix routes resolved against the run's own
//          URL) · DEF-SHL-4283 (a screen reading the admin-only regional
//          endpoint) · DEF-CWP-3925 (mount under the REAL path pattern).
// ───────────────────────────────────────────────────────
// ⚠ **THIS FILE EXISTS BECAUSE TWO OTHER FILES SAID IT DID.**
// `RunResultPage.tsx`'s header named it under `Tests:`, and a comment in its
// body promised *"`RunResultPage.dom.test.tsx` asserts the boundary by ADDRESS:
// the day a volume runbook lands, that test names this file."* It had never
// been created. The page therefore had **no test of any kind** while two files
// described a specific one — hard-won law 1, *a comment claiming a guarantee is
// not the guarantee*, inside the work of the lane that wrote the law's own
// citation. `DEF-RBS-4335`.
//
// So every case here asserts something the page could get WRONG, and two of
// them are the promises those comments made.
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { RunResultPage } from "./RunResultPage";
import report from "./blocks/__fixtures__/rbs001-report.json";

const TENANT = "brazosbend";
const RUN_ID = "e3f1a0c2-77d0-4a6b-9d1e-8c4b2f0a1d55";
const RUN_PATH = `/${TENANT}/runbooks/configuration_check/runs/${RUN_ID}`;

// No auto-cleanup in this repo — `vite.config.ts` registers no `setupFiles`,
// and every "exactly once" assertion below depends on this line.
afterEach(cleanup);

const RUN_ROW = {
  runbook_key: "configuration_check",
  runbook_name: "Configuration check",
  status: "succeeded",
  // 13:12 UTC is 08:12 in America/Chicago — the tenant's zone, which is the
  // whole point of asserting the rendered string rather than the instant.
  started_at: "2026-09-06T13:12:00Z",
  // ⚠ A FLOAT, BECAUSE THAT IS WHAT THE SERVER SERVES. The first fixture here
  // said `12`, which is the one value that makes the bug invisible: the tile
  // read `TOOK 8.933829s` on the real screen (`DEF-RBS-4341`) and every test
  // passed. A fixture rounded to what the screen should show cannot see a
  // screen that fails to round.
  took_seconds: 8.933829,
  has_report: true,
};

interface Call {
  path: string;
}

/** A client that answers by PATH and records what it was asked for.
 *
 *  The recording half is not decoration: two of the cases below are about a
 *  request that must NOT be made, and an absence is invisible to every
 *  assertion that only looks at the screen. */
function recordingClient(
  answers: Record<string, unknown>,
  status = 200,
): { client: ApiClient; calls: Call[] } {
  const calls: Call[] = [];
  const respond = async <T,>(path: string): Promise<ApiResponse<T>> => {
    calls.push({ path });
    const body = answers[path];
    if (body === undefined) {
      throw new Error(`no stub for ${path}`);
    }
    return { status, data: body as T, etag: null, notModified: false };
  };
  const client = {
    request: respond,
    get: respond,
    post: respond,
    put: respond,
    patch: respond,
    delete: respond,
  } as unknown as ApiClient;
  return { client, calls };
}

const ANSWERS: Record<string, unknown> = {
  [`/runbooks/runs/${RUN_ID}`]: RUN_ROW,
  [`/runbooks/runs/${RUN_ID}/report`]: { blocks: report },
};

function mount(client: ApiClient) {
  // ⚠ **AT THE REAL ADDRESS, UNDER THE REAL ROUTE PATTERN — `DEF-CWP-3925`.**
  // A page mounted bare gets `undefined` from `useParams` and builds every
  // address as `//host/…`, which is a protocol-relative URL to another host and
  // reads as a perfectly good string to `toContain`.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <ToastProvider>
          <MemoryRouter initialEntries={[RUN_PATH]}>
            <Routes>
              <Route
                path="/:tenant/runbooks/:key/runs/:runId"
                element={<RunResultPage client={client} />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
}

describe("RBS-006 — the page that feeds the renderer", () => {
  it("maps the run ROW onto the page head, in the tenant's own zone and format", async () => {
    const { client } = recordingClient(ANSWERS);
    mount(client);

    // 13:12 UTC → 08:12 Chicago, arranged MM/DD/YYYY. A screen that rendered
    // the instant, or fell through to UTC, prints 13:12 here — which is
    // `DEF-SHL-3964`'s whole failure and why the zone is asserted as a STRING a
    // clerk would read rather than as a prop that was passed.
    await waitFor(() => {
      expect(screen.getByText(/09\/06\/2026 08:12/)).toBeTruthy();
    });
    expect(screen.getAllByText(/Configuration check/).length).toBeGreaterThan(0);
    // `took_seconds` is a fact about the RUN, not about the frozen report.
    expect(screen.getByText("9s")).toBeTruthy();
  });

  it("can be named from the DOM — data-screen=RBS-006 on its root — DEF-RBS-4332", async () => {
    // Filed by a sibling wave's walkthrough, which clicked `Watch` on RBS-001's
    // in-flight banner, arrived here, and had nothing to wait for. It weakened
    // itself to an address assertion and SAID SO in its own comment, which is
    // the honest thing to do and is also why the defect got filed rather than
    // buried. This is the assertion that makes the weakening unnecessary.
    const { container } = mount(recordingClient(ANSWERS).client);
    await waitFor(() => {
      expect(container.querySelector('[data-screen="RBS-006"]')).toBeTruthy();
    });
    expect(
      container.querySelector('[data-screen="RBS-006"]')?.getAttribute("data-runbook"),
    ).toBe("Configuration check");
  });

  it("draws the FOUR KPI tiles RBS-006-R1 asks for, the run's duration last — DEF-RBS-4336", async () => {
    // ⚠ **COUNTED AGAINST THE WIREFRAME, NOT AGAINST THE PAYLOAD.** Region 2 of
    // `RBS-006-R1` is four tiles — *3 Blockers · 6 Warnings · 7 of 10 Steps
    // clear · 12s Took* — and the engine composes three, correctly: a duration
    // is a fact about the RUN and the report is frozen at close
    // (`BR-RBS-020`). The fourth is added at render time. Every payload-shaped
    // check agrees with three, which is why nothing could see the tile missing.
    const { container } = mount(recordingClient(ANSWERS).client);

    await waitFor(() => {
      expect(container.querySelectorAll(".kpi").length).toBeGreaterThan(0);
    });
    const tiles = Array.from(container.querySelectorAll(".kpi"));
    expect(tiles.length, "RBS-006-R1 region 2 is four tiles").toBe(4);
    expect(tiles[3]?.textContent).toContain("Took");
    expect(tiles[3]?.textContent, "a raw float reached the tile").not.toContain("8.93");
    expect(tiles[3]?.textContent).toContain("9s");
  });

  it("makes every fix route ABSOLUTE against the tenant, not against the run's own URL — DEF-RBS-4329", async () => {
    // ⚠ **THIS IS THE CASE THAT DID NOT EXIST WHEN THE DEFECT SHIPPED.**
    // Runbooks emit their fix routes tenant-relative (`plans-rates`), exactly
    // as `tenancy.selectors.CHECKLIST_TARGETS` does. React Router resolves a
    // relative `to` against the CURRENT route, so from this page's address the
    // link became
    // `/brazosbend/runbooks/configuration_check/runs/<id>/plans-rates` and
    // opened onto "This screen is not built yet."
    //
    // Asserted at the PAGE, because the page is the only thing that knows the
    // tenant — the block-level test can only check the context it is handed.
    const { client } = recordingClient(ANSWERS);
    const { container } = mount(client);

    await waitFor(() => {
      expect(container.querySelector("[data-fix-route]")).toBeTruthy();
    });
    const hrefs = Array.from(container.querySelectorAll("[data-fix-route]")).map((a) =>
      a.getAttribute("href"),
    );
    expect(hrefs.length).toBeGreaterThan(0);
    for (const href of hrefs) {
      // The WHOLE address, anchored. A suffix check (`endsWith`) is exactly
      // what let the defect through: a wrongly prefixed href still ends in the
      // route it was supposed to name.
      expect(href, "a fix route lost its tenant, or gained the run's path").toMatch(
        new RegExp(`^/${TENANT}/[a-z0-9-]+(/[a-z0-9-]+)*$`),
      );
      expect(href, "the fix route was resolved against the run's own URL").not.toContain("/runs/");
    }
    expect(hrefs).toContain(`/${TENANT}/plans-rates`);
  });

  it("reads the run and its report, and NOTHING else — the records boundary, by address", async () => {
    // ⚠ **THE PROMISE `RunResultPage.tsx` MAKES IN ITS OWN COMMENT.**
    // `GET /runbooks/runs/{id}/records` serves the per-record plan and outcome
    // rows a VOLUME runbook writes (`BR-RBS-035`). No runbook writes one yet,
    // so wiring it would be a query against a table this product cannot fill.
    // The day a volume runbook lands, this case goes red and names the file
    // that has to change — which is what a boundary asserted by ADDRESS is for.
    const { client, calls } = recordingClient(ANSWERS);
    mount(client);

    await waitFor(() => {
      expect(screen.getByText("9s")).toBeTruthy();
    });
    const paths = calls.map((c) => c.path);
    expect(paths).toContain(`/runbooks/runs/${RUN_ID}`);
    expect(paths).toContain(`/runbooks/runs/${RUN_ID}/report`);
    expect(
      paths.filter((p) => p.endsWith("/records")),
      "records paging goes no further than the frozen report until a VOLUME runbook exists",
    ).toEqual([]);
  });

  it("never reads the admin-only regional endpoint — DEF-SHL-4283", async () => {
    // Nine components read `GET /settings/regional` directly, and a Billing
    // Clerk meets a refusal on every one. This page takes the zone and the
    // format from the shell's own published settings instead, so the assertion
    // is about a call that must NOT be made.
    const { client, calls } = recordingClient(ANSWERS);
    mount(client);

    await waitFor(() => {
      expect(screen.getByText("9s")).toBeTruthy();
    });
    expect(calls.map((c) => c.path).filter((p) => p.includes("regional"))).toEqual([]);
  });

  it("a run still going cannot be re-run, and the control says why in six words or fewer", async () => {
    // B14 rule 33: a refusal sentence caps at five or six words. B14 also draws
    // a control a user may not use as DISABLED WITH its reason, never hidden —
    // hard-won law 2's mirror is a control that refuses over a live screen, and
    // this is the honest opposite: a refusal that is still true.
    const { client } = recordingClient({
      ...ANSWERS,
      [`/runbooks/runs/${RUN_ID}`]: { ...RUN_ROW, status: "running", took_seconds: null },
    });
    const { container } = mount(client);

    await waitFor(() => {
      expect(container.querySelector("[data-fix-route]")).toBeTruthy();
    });
    const disabled = Array.from(container.querySelectorAll("button")).filter(
      (b) => b.disabled,
    );
    expect(disabled.length).toBeGreaterThan(0);
    const reason = disabled.map((b) => b.getAttribute("title") ?? b.textContent ?? "").join(" ");
    expect(reason.trim().length).toBeGreaterThan(0);
  });
});
