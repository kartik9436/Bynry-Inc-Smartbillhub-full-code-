// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 5, lane PERFORMANCE — P5.1 (the headline agrees
//           with its rows; the 72 h default), P5.3 (the at-risk board), P5.4
//           (the schedule board), P5.5 (bulk raise across buildings).
// Defects:  DEF-WRK-9586 (the headline) · DEF-WRK-9656 (the pager moved nothing)
// Shapes:   every server answer below is a RECORDING from
//           `10-scripts/cr168_capture_work_shapes.py` (`../__fixtures__/`),
//           except the asset rows, which are the Assets module's own
//           `AssetRow` (no Work recording reads `/assets`) — said here rather
//           than passed off as recorded.
// ───────────────────────────────────────────────────────
//
// RED FIRST, on the tip `3cd891cfb` (this file copied into a worktree there):
// the file did not load — `Failed to resolve import "./RaiseAcrossBoard"`, the
// boards did not exist. With the board cases cut away, the old screen failed
// the two P5.1 / DEF-WRK-9656 cases — `Unable to find an element with the
// text: work.performance.tile.slaKept` and `expected undefined to be 1` (no
// page was sent) — and passed the two that are SRV-4's server half (the
// recording's tiles are its rows' sum; one row per job type). Quoted in
// CR-168 §21.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";
import type { ApiClient, ApiResponse } from "@/api/client";
import type { AssetRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { PerformancePage } from "../PerformancePage";
import { AtRiskPage } from "../AtRiskPage";
import type { Candidate } from "../workEndpoints";
import { acrossBody } from "./RaiseAcrossBoard";
import { holderLoad, dropMoments, giveBody } from "./ScheduleBoard";
import { spanText } from "./AtRiskBoard";
import PERFORMANCE_PAGED from "../__fixtures__/server/work.performance.paged.json";
import AT_RISK from "../__fixtures__/server/work.at-risk.json";
import SETTINGS_SLA from "../__fixtures__/server/work.settings.sla.json";
import ORDERS from "../__fixtures__/server/work-orders.list.json";
import CANDIDATES from "../__fixtures__/work-raise-candidates.recorded.json";
import RAISE_TEMPLATES from "../__fixtures__/work-templates-for-the-raise.recorded.json";
import BULK_RAISE from "../__fixtures__/work-orders-bulk-raise.recorded.json";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params as never) as unknown as string;

type Call = { method: string; path: string; query: Record<string, unknown>; body?: unknown };

/** Two assets in two different buildings — the Assets module's `AssetRow`. */
function asset(id: string, assetNo: string, where: string): AssetRow {
  return {
    id,
    asset_no: assetNo,
    serial_no: null,
    type: "meter",
    type_name: "Meter",
    tab: "meters",
    status: "in_service",
    status_name: "In service",
    behavior_class: "in_service",
    meter_type: null,
    meter_type_name: null,
    read_method: null,
    read_method_name: null,
    multiplier: "1",
    size_class: null,
    unit: null,
    net_metering: false,
    manufacturer: null,
    model: null,
    install_date: null,
    parent_asset_no: null,
    service_point_id: null,
    assigned_unit_id: null,
    assigned_to: null,
    assigned_address: where,
    assigned: true,
    test_due: true,
    retire_date: null,
    retire_reason: null,
    replaced_by: null,
    actions: [],
    next_test: "2026-09-30",
  };
}
const ASSETS = { count: 2, next: null, previous: null, results: [asset("a-1", "W-5040", "14 Willow Bend"), asset("a-2", "W-6010", "8 Quarry Lane")] };

function server(overrides: Partial<Record<string, unknown>> = {}): { client: ApiClient; calls: Call[] } {
  const calls: Call[] = [];
  const bodies: Record<string, unknown> = {
    "/work/performance": PERFORMANCE_PAGED,
    "/work/settings/sla": SETTINGS_SLA,
    "/work/at-risk": AT_RISK,
    "/work-orders": ORDERS,
    "/work/candidates": CANDIDATES,
    "/work/templates": RAISE_TEMPLATES,
    "/assets": ASSETS,
    ...overrides,
  };
  const get = async (path: string, options?: { query?: Record<string, unknown> }): Promise<ApiResponse<unknown>> => {
    calls.push({ method: "GET", path, query: options?.query ?? {} });
    if (!(path in bodies)) throw new Error(`no recording for GET ${path}`);
    const body = bodies[path];
    return { status: 200, data: typeof body === "function" ? (body as (q: unknown) => unknown)(options?.query) : body, etag: null, notModified: false };
  };
  const post = async (path: string, body: unknown): Promise<ApiResponse<unknown>> => {
    calls.push({ method: "POST", path, query: {}, body });
    if (path === "/work-orders/bulk-raise") return { status: 200, data: BULK_RAISE, etag: null, notModified: false };
    const ids = (body as { ids: string[] }).ids;
    return {
      status: 200,
      data: { act: "assign", results: ids.map((id) => ({ id, ok: true })), done: ids.length, failed: 0 },
      etag: null,
      notModified: false,
    };
  };
  return { client: { get, post } as unknown as ApiClient, calls };
}

function mount(path: string, element: ReactElement, atRisk?: ReactElement) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/:tenant/work/performance" element={element} />
            {/* §30 — the At risk tab's real path pattern (law 2's fixture
                clause: mount a routed screen under its real path). */}
            <Route path="/:tenant/work/at-risk" element={atRisk ?? <p data-landed-at-risk="" />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => cleanup());

describe("P5.1 — the headline is its rows' sum (DEF-WRK-9586), with the 72 h default", () => {
  it("the recording's tiles equal the sum of its rows — volume, measured and kept", () => {
    // The whole period fits one page here, so the rows ARE the set.
    expect(PERFORMANCE_PAGED.count).toBe(PERFORMANCE_PAGED.results.length);
    const sum = (key: "volume" | "sla_measured" | "sla_met") =>
      PERFORMANCE_PAGED.results.reduce((total, row) => total + row[key], 0);
    expect(sum("volume")).toBe(PERFORMANCE_PAGED.tiles.volume);
    expect(sum("sla_measured")).toBe(PERFORMANCE_PAGED.tiles.sla_measured);
    expect(sum("sla_met")).toBe(PERFORMANCE_PAGED.tiles.sla_met);
  });

  it("the SLA tile says how many of how many, and the default promise for an undated job", async () => {
    const { client } = server();
    mount(`/${TENANT}/work/performance`, <PerformancePage client={client} />);
    const kept = await screen.findByText(
      t("work.performance.tile.slaKept", { met: PERFORMANCE_PAGED.tiles.sla_met, measured: PERFORMANCE_PAGED.tiles.sla_measured }),
    );
    expect(kept).toBeTruthy();
    expect(await screen.findByText(t("work.performance.tile.slaDefault", { hours: SETTINGS_SLA.hours }))).toBeTruthy();
    expect(t("work.performance.tile.slaDefault", { hours: 72 })).toBe("Undated: 72 h promise");
  });

  it("draws one row per recorded job type, read from `results`", async () => {
    const { client } = server();
    mount(`/${TENANT}/work/performance`, <PerformancePage client={client} />);
    await screen.findAllByText(PERFORMANCE_PAGED.results[0].job_type);
    const table = screen.getAllByRole("table")[0];
    for (const row of PERFORMANCE_PAGED.results) expect(within(table).getAllByText(row.job_type).length).toBeGreaterThan(0);
  });
});

describe("DEF-WRK-9656 — the page, the size and the sort reach the server (NFR-3)", () => {
  it("asks for page 1 of 50, then page 2 when the pager moves", async () => {
    const big = { ...PERFORMANCE_PAGED, count: 120 };
    const { client, calls } = server({ "/work/performance": big });
    mount(`/${TENANT}/work/performance`, <PerformancePage client={client} />);
    await screen.findAllByText(PERFORMANCE_PAGED.results[0].job_type);
    const first = calls.find((c) => c.path === "/work/performance");
    expect(first?.query.page).toBe(1);
    expect(first?.query.per).toBe(50);
    expect(first?.query.sort).toBe("volume");
    const next = screen.getAllByRole("button").find((b) => /next/i.test(b.getAttribute("aria-label") ?? ""));
    expect(next).toBeTruthy();
    fireEvent.click(next as HTMLElement);
    await waitFor(() => expect(calls.some((c) => c.path === "/work/performance" && c.query.page === 2)).toBe(true));
  });
});

describe("P5.3 — the at-risk board, its own tab since §30", () => {
  it("draws the recorded jobs soonest first, with the server's window", async () => {
    const { client } = server();
    mount(`/${TENANT}/work/at-risk`, <PerformancePage client={client} />, <AtRiskPage client={client} />);
    expect(await screen.findByText(t("work.atRisk.fact", { count: AT_RISK.count, hours: AT_RISK.window_hours }))).toBeTruthy();
    for (const row of AT_RISK.results.slice(0, 10)) expect(screen.getAllByText(row.order_no).length).toBeGreaterThan(0);
    expect(document.querySelectorAll("[data-promise='left']").length).toBe(AT_RISK.results.length);
  });

  it("a job past its promise reads Late, in the danger pill", async () => {
    const late = {
      ...AT_RISK,
      count: 1,
      results: [{ ...AT_RISK.results[0], promise: { ...AT_RISK.results[0].promise, overdue: true, minutes_left: -320 } }],
    };
    const { client } = server({ "/work/at-risk": late });
    mount(`/${TENANT}/work/at-risk`, <PerformancePage client={client} />, <AtRiskPage client={client} />);
    expect(await screen.findByText("Late 5 h 20 m")).toBeTruthy();
  });

  it("§30 — the 2.514.0 address forwards to the At risk TAB, by address", async () => {
    const { client } = server();
    mount(`/${TENANT}/work/performance?view=at-risk`, <PerformancePage client={client} />);
    expect(await screen.findByText((_, el) => el?.hasAttribute("data-landed-at-risk") ?? false)).toBeTruthy();
    expect(document.querySelector("[data-performance-view]")).toBeNull();
  });

  it("§30 — Performance offers Results, Schedule and Raise across, and no At risk view", async () => {
    const { client } = server();
    mount(`/${TENANT}/work/performance`, <PerformancePage client={client} />);
    await screen.findByText(t("work.performance.view.schedule.label"));
    expect(screen.getByText(t("work.performance.view.across.label"))).toBeTruthy();
    expect(screen.queryByText(t("work.tabs.atRisk"), { selector: "button" })).toBeNull();
    expect(document.querySelector('[data-segment="at-risk"], [value="at-risk"]')).toBeNull();
  });

  it("words a span by its two largest units", () => {
    expect(spanText(t, 4177)).toBe("2 d 21 h");
    expect(spanText(t, -320)).toBe("5 h 20 m");
    expect(spanText(t, 40)).toBe("40 m");
  });
});

describe("P5.4 — the schedule board", () => {
  const candidate = (patch: Partial<Candidate["advice"]>): Candidate => ({
    ...(CANDIDATES.results[0] as unknown as Candidate),
    advice: { ...(CANDIDATES.results[0].advice as Candidate["advice"]), ...patch },
  });

  it("over-assigned is off-with-jobs, or over the daily limit (§30) — nothing else", () => {
    expect(holderLoad(candidate({ off_that_day: true, jobs_that_day: 2 }))).toBe("over");
    expect(holderLoad(candidate({ off_that_day: true, jobs_that_day: 0 }))).toBe("off");
    expect(holderLoad(candidate({ off_that_day: false, jobs_that_day: 9 }))).toBe("busy");
    expect(holderLoad(candidate({ off_that_day: false, jobs_that_day: 0 }))).toBe("free");
    // The PO's worked case: limit 6, seven jobs — over; six — not.
    expect(holderLoad(candidate({ jobs_that_day: 7, daily_job_limit: 6, over_daily_limit: true }))).toBe("limit");
    expect(holderLoad(candidate({ jobs_that_day: 6, daily_job_limit: 6, over_daily_limit: false }))).toBe("busy");
  });

  it("§30 — D. Ortiz with 7 jobs and a limit of 6 reads red, beside Off, has jobs", async () => {
    const ortiz = {
      ...CANDIDATES.results[0],
      name: "D. Ortiz",
      advice: { ...CANDIDATES.results[0].advice, off_that_day: false, jobs_that_day: 7, daily_job_limit: 6, over_daily_limit: true },
    };
    const { client } = server({ "/work/candidates": { ...CANDIDATES, count: 1, results: [ortiz] } });
    mount(`/${TENANT}/work/performance?view=schedule`, <PerformancePage client={client} />);
    const pill = await screen.findByText(t("work.schedule.load.overLimit", { limit: 6 }));
    expect(pill.closest("[data-holder-load]")?.getAttribute("data-holder-load")).toBe("limit");
    expect(pill.className).toMatch(/\bpast\b/u); // the kit's danger tone
    expect(document.querySelector('[data-holder-jobs="D. Ortiz"]')?.textContent).toBe("7");
  });

  it("a drop writes the day's window — morning, afternoon, or the whole day", () => {
    expect(dropMoments("2026-10-05", "morning")).toEqual({ window_start: "2026-10-05T08:00:00", window_end: "2026-10-05T12:00:00" });
    expect(dropMoments("2026-10-05", "any")).toEqual({ window_start: "2026-10-05T00:00:00", window_end: "2026-10-05T23:59:00" });
    const crew = CANDIDATES.results.find((c) => c.kind === "crew") as unknown as Candidate;
    expect(giveBody(["x"], crew, "2026-10-05", "afternoon")).toMatchObject({ act: "assign", ids: ["x"], crew_id: crew.id });
  });

  it("asks for everybody's load on the chosen day, and the jobs nobody holds", async () => {
    const { client, calls } = server();
    mount(`/${TENANT}/work/performance?view=schedule`, <PerformancePage client={client} />);
    await screen.findAllByText(CANDIDATES.results[0].name);
    expect(calls.find((c) => c.path === "/work-orders")?.query.technician).toBe("none");
    expect(String(calls.find((c) => c.path === "/work/candidates")?.query.on ?? "")).toMatch(/^\d{4}-\d{2}-\d{2}$/u);
  });

  it("tick a job and press Give ✓ — one assign, the holder and the morning window", async () => {
    const { client, calls } = server();
    mount(`/${TENANT}/work/performance?view=schedule`, <PerformancePage client={client} />);
    await screen.findAllByText(CANDIDATES.results[0].name);
    const first = ORDERS.results[0];
    fireEvent.click(screen.getByLabelText(t("work.schedule.tickJob", { order: first.order_no })));
    const give = document.querySelector(`[data-give-to="${CANDIDATES.results[0].name}"]`) as HTMLButtonElement;
    expect(give.disabled).toBe(false);
    fireEvent.click(give);
    await waitFor(() => expect(calls.some((c) => c.path === "/work-orders/bulk")).toBe(true));
    const posted = calls.find((c) => c.path === "/work-orders/bulk")?.body as Record<string, unknown>;
    expect(posted).toMatchObject({ act: "assign", ids: [first.id], technician_id: CANDIDATES.results[0].id });
    expect(String(posted.window_start)).toMatch(/T08:00:00$/u);
  });

  it("drag a job onto a holder — the same one assign", async () => {
    const { client, calls } = server();
    mount(`/${TENANT}/work/performance?view=schedule`, <PerformancePage client={client} />);
    await screen.findAllByText(CANDIDATES.results[1].name);
    const job = ORDERS.results[2];
    const store: Record<string, string> = {};
    const dataTransfer = { setData: (k: string, v: string) => (store[k] = v), getData: (k: string) => store[k] ?? "", effectAllowed: "" };
    // DEF-WRK-9657 — an order number never breaks onto two lines ("WO-" /
    // "0018"). jsdom cannot measure, so the class that holds it is asserted;
    // the 1440 walk measures the height (fix6_after_walk.mjs).
    expect(document.querySelector(`[data-drag-order="${job.order_no}"]`)?.className).toContain("whitespace-nowrap");
    fireEvent.dragStart(document.querySelector(`[data-drag-order="${job.order_no}"]`) as Element, { dataTransfer });
    const target = document.querySelector(`[data-drop-holder="${CANDIDATES.results[1].name}"]`) as Element;
    fireEvent.dragOver(target, { dataTransfer });
    fireEvent.drop(target, { dataTransfer });
    await waitFor(() => expect(calls.some((c) => c.path === "/work-orders/bulk")).toBe(true));
    expect(calls.find((c) => c.path === "/work-orders/bulk")?.body).toMatchObject({ ids: [job.id], technician_id: CANDIDATES.results[1].id });
  });
});

describe("P5.5 — bulk raise across buildings", () => {
  it("the body names the assets and NO premises — each walks to its own building", () => {
    const template = RAISE_TEMPLATES.results[0] as never;
    const body = acrossBody(template, ["a-1", "a-2"], "", "k-1");
    expect(body.asset_ids).toEqual(["a-1", "a-2"]);
    expect("premises_id" in body).toBe(false);
    expect(body.type).toBe(RAISE_TEMPLATES.results[0].name);
  });

  it("choose a template, tick two assets in two buildings, raise two jobs", async () => {
    const { client, calls } = server();
    mount(`/${TENANT}/work/performance?view=across`, <PerformancePage client={client} />);
    const select = (await screen.findByText(t("work.across.templatePick"))).closest("select") as HTMLSelectElement;
    await waitFor(() => expect(select.options.length).toBeGreaterThan(1));
    const template = RAISE_TEMPLATES.results.find((row) => row.service?.code === "water") ?? RAISE_TEMPLATES.results[0];
    fireEvent.change(select, { target: { value: template.id } });
    await screen.findByText("W-5040");
    const read = calls.filter((c) => c.path === "/assets").at(-1);
    expect(read?.query).toMatchObject({ "f.assigned": "true", "f.test_due": "true", "f.service": template.service?.code, page: 1, per: 50 });
    fireEvent.click(screen.getByLabelText(t("work.raise.tick", { unit: "W-5040" })));
    fireEvent.click(screen.getByLabelText(t("work.raise.tick", { unit: "W-6010" })));
    fireEvent.click(document.querySelector("[data-across-raise]") as Element);
    await waitFor(() => expect(calls.some((c) => c.path === "/work-orders/bulk-raise")).toBe(true));
    const posted = calls.find((c) => c.path === "/work-orders/bulk-raise")?.body as Record<string, unknown>;
    expect(posted.asset_ids).toEqual(["a-1", "a-2"]);
    expect(posted.premises_id).toBeUndefined();
    expect(await screen.findByText(t("work.raise.resultTitle", { count: BULK_RAISE.done }))).toBeTruthy();
    // DEF-WRK-9658 — each job number in the result opens its order, as every
    // other Work result does; it was plain text.
    for (const result of BULK_RAISE.results) {
      const link = screen.getByText(result.order_no as string).closest("a");
      expect(link?.getAttribute("href")).toBe(`/${TENANT}/work/orders/${result.order_no}`);
    }
  });

  it("the raise is disabled and says why until a template and an asset are chosen", async () => {
    const { client } = server();
    mount(`/${TENANT}/work/performance?view=across`, <PerformancePage client={client} />);
    const button = (await screen.findByText(t("work.raise.commit", { count: 0 }))).closest("button") as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(screen.getByText(t("work.across.needTemplate"))).toBeTruthy();
  });
});
