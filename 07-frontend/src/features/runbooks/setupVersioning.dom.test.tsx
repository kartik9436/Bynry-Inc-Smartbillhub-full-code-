// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1 (`DEF-523`). `vite.config.ts`
// keeps the default environment at `node`, and an interactive suite opts in per file.
// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-040 (EP-RBS-01) — CR-075 wave E task E5, the pass over the
//          SCREENS for the two signed cases about versions.
// Screens: RBS-004 (`S150`) at `/{tenant}/runbooks/{key}`, tabs at `#activity` …
// Rules:   `07-endpoints.md` rows 2, 3, 8 · `BR-RBS-038` (a run pins its
//          version; a template change is OFFERED, never applied) ·
//          `BR-RBS-036` (the trust ratchet) · B14 rule 31 · `NFR-3`.
// Defects: DEF-RBS-4308 (the wire and the view model never met) ·
//          DEF-RBS-4311 (a live route behind a dead control) ·
//          DEF-CWP-3925 (mount under the REAL path pattern).
// Cases:   TC-RBS-13 · TC-RBS-24 — the SCREEN halves. The engine halves are
//          `06-backend/tests/test_us_rbs_038_definition_surface.py`.
// ───────────────────────────────────────────────────────
// `E5` — THE PASS OVER THE SCREENS, AND WHY THE ENGINE'S ASSERTIONS ARE NOT
// ENOUGH ON THEIR OWN.
//
// The backend already proves that an old run keeps its version and its report
// byte for byte, that the next run is at v4, and that a template bump changes
// nothing on the copy. Every one of those is a claim about the DATABASE. None
// of them is a claim about what a person sees, and `DEF-RBS-4308` is exactly
// what that gap costs: the engine was right, the screen threw, and both suites
// were green.
//
// So each case here asks the screen question that the database question leaves
// open:
//
//   * `TC-RBS-13` — *"editing a runbook after a run leaves that run's stored
//     version and plan unchanged"*, whose named anti-case is **the definition
//     read live at display time**. On a screen that means: does `RBS-006` ever
//     ASK for the definition? An absence is invisible to every assertion that
//     only looks at rendered output, so the client here RECORDS what it was
//     asked for and the test reads the list.
//   * `TC-RBS-24` — *"the copy shows Template updated and its steps are
//     unchanged"*, whose anti-case is **the copy silently gaining the step**.
//     On a screen that is a count: the Steps tab still draws the copy's own
//     steps while the offer is on screen beside them.
//
// ══════════════════════════════════════════════════════════════════════════
// MOUNTED AT THE REAL ADDRESS, UNDER THE REAL ROUTE PATTERN
// ══════════════════════════════════════════════════════════════════════════
// `DEF-CWP-3925`: a page mounted bare in a `MemoryRouter` gets `undefined` from
// `useParams` and builds every address as `//host/…` — a protocol-relative URL
// to another host that reads as a perfectly good string to `toContain`. And
// `DEF-RBS-4329`, today: a relative `<Link to>` resolved against `/` gives the
// right answer for the wrong reason and hides a broken link.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { RunbookSetupPage } from "./RunbookSetupPage";
import type { RunbookDetailBody, WireActivity } from "./setupWire";

const TENANT = "brazosbend";
const KEY = "commercial-accounts";
const PATH = `/${TENANT}/runbooks/${KEY}`;

// No auto-cleanup in this repo — `vite.config.ts` registers no `setupFiles`, so
// every render is ADDED to the same document and every "exactly N" assertion
// below depends on this line.
afterEach(cleanup);

/** The four versions `RBS-004.7` draws, newest first, as the ENGINE serves
 *  them: facts, never a sentence (`selectors.runbook_activity`). */
const ACTIVITY: WireActivity[] = [
  {
    id: 4,
    version: 4,
    changes: [{ field: "cap", from: 100, to: 400 }],
    actor: { name: "Dana Whitfield" },
    when: "2026-09-02T14:05:00Z",
  },
  {
    id: 3,
    version: 3,
    changes: [{ field: "enabled", from: true, to: false }],
    actor: { name: "Ray Perez" },
    when: "2026-08-26T09:00:00Z",
  },
  {
    id: 2,
    version: 2,
    changes: [{ field: "cron", from: null, to: "0 7 * * 1" }],
    actor: { name: "Dana Whitfield" },
    when: "2026-08-12T16:40:00Z",
  },
  {
    id: 1,
    version: 1,
    changes: [
      { field: "origin", to: "cloned" },
      { field: "cloned_from", to: "Dunning" },
    ],
    actor: { name: "Dana Whitfield" },
    when: "2026-08-12T16:38:00Z",
  },
];

function body(overrides: Partial<RunbookDetailBody> = {}): RunbookDetailBody {
  return {
    // `BR-RBS-042`, wave `T`: the server always sends this list. Empty is the
    // honest value here — these cases are about VERSIONS, not inputs, and this
    // clone's template is not in the registry a test registry stands in for.
    parameters: [],
    key: KEY,
    name: "Commercial accounts",
    kind: "action",
    category: "collections",
    tags: [],
    origin: "cloned",
    template_key: "dunning",
    subject_type: "account",
    unit_of_work: "account",
    enabled: false,
    current_version: 4,
    schedule: {
      trigger_kind: "schedule",
      cron: "0 7 * * 1",
      event_kind: null,
      timezone: "America/Chicago",
      next_run: null,
    },
    cap: 400,
    gate_mode: "approve_each_run",
    visible_to_roles: null,
    roles: ["system_admin", "billing_clerk"],
    trusted_version: 3,
    dry_run_only: true,
    template_update: null,
    activity: ACTIVITY,
    definition: {
      key: "dunning",
      name: "Dunning and notices",
      kind: "action",
      category: "collections",
      subject_type: "account",
      unit_of_work: "account",
      triggers: ["schedule", "manual"],
      tags: [],
      parameters: [],
      steps: [{ key: "find", label: "Find accounts past due", mode: "set", writes: false }],
      guards: [{ key: "medical", label: "Medical protection" }],
      requires: null,
      ports: ["notify_email"],
    },
    guards: [{ key: "medical", label: "Medical protection" }],
    ports: ["notify_email"],
    writes_nothing: false,
    requires: null,
    last_run: null,
    open_items: 0,
    ...overrides,
  };
}

interface Call {
  method: string;
  path: string;
  body?: unknown;
  /** ⚠ **THE QUERY TRAVELS IN THE OPTIONS, NOT IN THE PATH**, and the first
   *  draft of this stub recorded only the path — so the case asserting
   *  `f.runbook` failed against `/runbooks/runs` and would have passed if it
   *  had been written the other way round (`not.toContain`). `readListPage`
   *  hands `{query}` to `client.get`, which is where the filter is. */
  query?: Record<string, unknown>;
}

/**
 * A client that answers by PATH and RECORDS every call.
 *
 * The recording half is not decoration: `TC-RBS-13`'s named anti-case is *the
 * definition read live at display time*, which is a request that must NOT be
 * made — and an absence is invisible to every assertion that only looks at the
 * screen.
 */
function recordingClient(detail: RunbookDetailBody, runs: unknown = { count: 0, results: [] }) {
  const calls: Call[] = [];
  let current = detail;
  const answer = async <T,>(
    method: string,
    path: string,
    payload?: unknown,
    options?: { query?: Record<string, unknown> },
  ): Promise<ApiResponse<T>> => {
    calls.push({ method, path, body: payload, query: options?.query });
    if (path.startsWith("/runbooks/runs")) {
      return { status: 200, data: runs as T, etag: null, notModified: false };
    }
    if (path.startsWith(`/runbooks/${KEY}`)) {
      if (method === "put") {
        const edit = (payload ?? {}) as Record<string, unknown>;
        current = {
          ...current,
          ...("enabled" in edit ? { enabled: Boolean(edit.enabled) } : {}),
          ...("cap" in edit ? { cap: edit.cap as number | null } : {}),
          ...(edit.accept_template_update === true ? { template_update: null } : {}),
          current_version: current.current_version + 1,
        };
      }
      return { status: 200, data: current as T, etag: null, notModified: false };
    }
    throw new Error(`no stub for ${method} ${path}`);
  };
  const client = {
    request: (p: string, o?: { query?: Record<string, unknown> }) => answer("request", p, undefined, o),
    get: (p: string, o?: { query?: Record<string, unknown> }) => answer("get", p, undefined, o),
    post: (p: string, b?: unknown) => answer("post", p, b),
    put: (p: string, b?: unknown) => answer("put", p, b),
    patch: (p: string, b?: unknown) => answer("patch", p, b),
    delete: (p: string) => answer("delete", p),
  } as unknown as ApiClient;
  return { client, calls };
}

function mount(client: ApiClient, hash = "") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "DD-MMM-YY" }}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`${PATH}${hash}`]}>
            <Routes>
              <Route path="/:tenant/runbooks/:key" element={<RunbookSetupPage client={client} />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
}

describe("E4 · RBS-004 draws the SERVER's payload — DEF-RBS-4308", () => {
  // The defect observed rather than reasoned about: `RunbookSetup` read
  // `view.capabilities.length` on `undefined` and React Router caught a
  // `TypeError` for the whole screen. A page of blanks would have been the
  // milder outcome.
  it("renders the runbook's own name over the real body, and does not throw", async () => {
    const { client } = recordingClient(body());
    const { container } = mount(client);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Commercial accounts" })).toBeTruthy();
    });
    expect(container.querySelector('[data-screen="RBS-004"]')).toBeTruthy();
    expect(container.querySelector('[data-screen="RBS-004"]')?.getAttribute("data-runbook")).toBe(
      KEY,
    );
  });

  // `NFR-3` and `api.py::runbook_detail`'s own ruling: the Runs tab is the
  // history route with a runbook filter, not a second paging surface on the
  // detail. A screen that sent `runs_page` to the detail route would be
  // describing one list twice — `G114`'s whole subject.
  it("asks the history route for the Runs tab, with this runbook's filter", async () => {
    const { client, calls } = recordingClient(body());
    mount(client, "#runs");
    await waitFor(() => expect(calls.length).toBeGreaterThan(1));
    const runsCall = calls.find((call) => call.path.startsWith("/runbooks/runs"));
    expect(runsCall?.query).toMatchObject({ "f.runbook": KEY, page: 1, per: 50 });
    // And NOT the C3 draft's second paging surface on the detail route.
    expect(
      calls.find((call) => JSON.stringify(call.query ?? {}).includes("runs_page")),
    ).toBeUndefined();
  });
});

describe("E5 · TC-RBS-24 — the copy's steps are unchanged after a template bump", () => {
  const OFFERED = body({
    template_update: { available: true, steps_added: 1, steps_removed: 0, other_changed: false },
  });

  // The anti-case `EP-RBS-01` names is *the copy silently gaining the step*. So
  // the assertion is a COUNT, taken while the offer is on screen beside it.
  it("draws the offer and still shows ONE step, not two", async () => {
    const { client } = recordingClient(OFFERED);
    const { container } = mount(client, "#steps");
    await waitFor(() => {
      expect(container.querySelector("[data-template-update]")).toBeTruthy();
    });
    expect(container.querySelectorAll("[data-step]")).toHaveLength(1);
    expect(screen.getByText("Find accounts past due")).toBeTruthy();
  });

  it("says how many steps are on offer, from the server's counts", async () => {
    const { client } = recordingClient(OFFERED);
    const { container } = mount(client, "#steps");
    await waitFor(() => {
      expect(container.querySelector("[data-template-update]")?.textContent).toContain(
        "Template updated",
      );
    });
    expect(container.querySelector("[data-template-update]")?.textContent).toContain("1");
  });

  // `BR-RBS-038` — *offered, never applied*. Pressing **Review →** is the only
  // thing in this product that applies it, and it goes through the edit route
  // rather than a nineteenth address.
  it("applies the offer ONLY when a person presses Review", async () => {
    const { client, calls } = recordingClient(OFFERED);
    const { container } = mount(client, "#steps");
    await waitFor(() => expect(container.querySelector("[data-template-update]")).toBeTruthy());
    // Nothing has been written by merely LOOKING at the offer.
    expect(calls.filter((call) => call.method === "put")).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: /Review/ }));
    await waitFor(() => {
      expect(calls.filter((call) => call.method === "put")).toHaveLength(1);
    });
    expect(calls.find((call) => call.method === "put")?.body).toEqual({
      accept_template_update: true,
    });
  });

  it("takes the offer off the screen once it is taken", async () => {
    const { client } = recordingClient(OFFERED);
    const { container } = mount(client, "#steps");
    await waitFor(() => expect(container.querySelector("[data-template-update]")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /Review/ }));
    await waitFor(() => {
      expect(container.querySelector("[data-template-update]")).toBeNull();
    });
  });
});

describe("E5 · TC-RBS-13 — an edit never rewrites what a past run shows", () => {
  // The named anti-case is *the definition read live at display time*. This
  // screen is the DEFINITION screen and it is allowed to read the definition;
  // the claim under test is the mirror — that the RESULT screen is fed by the
  // run and by nothing else. `RunResultPage.dom.test.tsx` asserts the two reads
  // it makes; this asserts that neither of them is the definition, which is the
  // half that could only be proved by looking at the whole list.
  it("the result screen's two reads are the RUN and its REPORT, never the definition", async () => {
    const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
      readFileSync(p: string, enc: string): string;
    };
    const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
      dirname(p: string): string;
      join(...p: string[]): string;
    };
    const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
      fileURLToPath(url: URL | string): string;
    };
    const here = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
    const source = nodeFs.readFileSync(nodePath.join(here, "RunResultPage.tsx"), "utf8");
    // A run's report is FROZEN at close (`BR-RBS-020`). The way a screen breaks
    // that is by reading the live definition and re-rendering the past from it,
    // so the check is that this file never names the definition route at all.
    expect(source).not.toMatch(/`\/runbooks\/\$\{[^}]*key[^}]*}`/);
    expect(source).toContain("/runbooks/runs/");
  });

  // The version a clerk and an auditor say out loud — *"it was v3 when that
  // went out"*. `08-screen-layouts.md` allows it under B14 rule 31's own escape
  // clause; the row's real id is never drawn.
  it("the Activity tab reads newest first: v4, v3, v2, v1", async () => {
    const { client } = recordingClient(body());
    const { container } = mount(client, "#activity");
    await waitFor(() => {
      expect(container.querySelector("[data-region='activity']")).toBeTruthy();
    });
    const versions = [...container.querySelectorAll("[data-activity-version]")].map(
      (node) => node.textContent,
    );
    expect(versions).toEqual(["v4", "v3", "v2", "v1"]);
  });

  // `E4` proper: the facts the engine serves become the sentence the sheet
  // draws. `RBS-004.7`'s own four, in its own order.
  it("composes each version's sentence from the engine's facts", async () => {
    const { client } = recordingClient(body());
    const { container } = mount(client, "#activity");
    await waitFor(() => expect(container.querySelector("[data-region='activity']")).toBeTruthy());
    const rows = [...container.querySelectorAll("[data-activity]")].map((n) => n.textContent ?? "");
    expect(rows[0]).toContain("Cap raised to 400");
    expect(rows[1]).toContain("Paused");
    expect(rows[2]).toContain("Schedule changed");
    expect(rows[3]).toContain("Copied from Dunning");
  });

  it("names the person and the moment, in the tenant's zone and format", async () => {
    const { client } = recordingClient(body());
    const { container } = mount(client, "#activity");
    await waitFor(() => expect(container.querySelector("[data-region='activity']")).toBeTruthy());
    const newest = container.querySelector("[data-activity]")?.textContent ?? "";
    expect(newest).toContain("Dana Whitfield");
    // 14:05 UTC on 2 Sep is 09:05 in America/Chicago — still the 2nd, and the
    // tenant's format is `DD-MMM-YY`.
    expect(newest).toContain("02-Sep-26");
  });

  // B14 rule 31 — the whole screen, over the whole payload.
  it("puts no uuid on the screen", async () => {
    const { client } = recordingClient(body());
    const { container } = mount(client, "#activity");
    await waitFor(() => expect(container.querySelector("[data-region='activity']")).toBeTruthy());
    expect(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/.test(
        container.textContent ?? "",
      ),
    ).toBe(false);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// WHAT IS DELIBERATELY *NOT* IN THIS FILE, AND WHERE IT IS INSTEAD
// ══════════════════════════════════════════════════════════════════════════
// This file had a third and fourth section — **Pause**, **Change limits** and
// the two hold-expiry clocks on **Run ▶** and **Change scope** — and they were
// deleted before it was pushed, because a sibling lane landed exactly those
// assertions in `RunbookSetupPage.test.tsx` at commit `c6fa557b`, minutes
// earlier and on top of this wave's own mapper commit.
//
// **Two files asserting one claim is the shape this repository keeps paying
// for** — `G114`'s subject one level down, and the reason `homeEndpoints.ts`
// refuses to describe the list envelope a second time. When they drift, both
// are green and neither is right. So the released controls are asserted THERE,
// once, and this file keeps the half that is `E5`'s and nobody else's: the two
// signed test cases about VERSIONS.
//
// Checked rather than assumed: `RunbookSetupPage.test.tsx` at `c6fa557b` holds
// *Resume writes `enabled`*, *Change limits writes the cap and the approval*,
// *an empty cap clears it rather than sending zero*, both still-held refusals,
// and *goes RED the day a run-starter or a scope writer joins the client*.
