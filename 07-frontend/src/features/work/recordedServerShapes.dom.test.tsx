// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 lane SHAPE-SWEEP — every Work back-office screen
//           mounted on what the REAL server sent, never on a typed-up reply.
// Defects:  DEF-WRK-9600 · DEF-WRK-9601 (the two that taught it) and the
//           sweep's own (CR-168 §15)
// Rules:    CLAUDE.md hard-won law 2's mirror · law 6 · law 7's *looking at
//           the wrong thing* · CR-168 §7 *"Fixtures come from the server"*
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY BODY THIS FILE SERVES IS A RECORDING.** `__fixtures__/server/*.json`
// is written by `10-scripts/cr168_capture_work_shapes.py` from
// `manage.py runserver` on PostgreSQL 16 after `seed_demo`,
// `load_sample_data --tenant brazosbend` and the round-2/3 seed scripts. On
// 2026-10-04 the order page crashed on every job with a unit and *Put on hold*
// offered no reason while every test was green, because the screen's tests
// served a reply the screen's own lane had typed — which could only ever agree
// with the screen. These cases serve the server's reply instead.
//
// `recordedServerShapes.typecheck.ts` makes `tsc` compare the same recordings
// with the screen's TYPES; this file proves the screens DRAW them. Both are
// needed: a type can be right and a screen can still filter every row away
// (`DEF-WRK-9601` was exactly that).
//
// ⚠ **THE WITNESSES ARE READ FROM THE RECORDING**, never typed here, so a
// re-recording on another seed moves them with it. Each case first proves it
// arrived (a value only the recorded body carries is on screen) — a screen
// that never mounted and a screen that mounted empty look identical to a
// `queryBy…` that returns null.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { AwaitingApprovalPage } from "./AwaitingApprovalPage";
import { CrewsPage } from "./CrewsPage";
import { MapView } from "./MapView";
import { OrderDetailPage } from "./OrderDetailPage";
import { OrderEditPage } from "./OrderEditPage";
import { OrdersPage } from "./OrdersPage";
import { PartsPage } from "./PartsPage";
import { PerformancePage } from "./PerformancePage";
import { TechnicianDetailPage } from "./TechnicianDetailPage";
import { TemplateDetailPage } from "./TemplateDetailPage";
import { TemplatesPage } from "./TemplatesPage";
import { listHoldReasons } from "./orderPage/orderPageEndpoints";

import ORDERS from "./__fixtures__/server/work-orders.list.json";
import ORDERS_DONE from "./__fixtures__/server/work-orders.list.complete.json";
import AWAITING from "./__fixtures__/server/work-orders.awaiting-approval.json";
import MAP from "./__fixtures__/server/work-orders.map.json";
import HOLD_REASONS from "./__fixtures__/server/work.hold-reasons.json";
import RAISE_OPTIONS from "./__fixtures__/server/work.raise-options.json";
import KPIS from "./__fixtures__/server/work.kpis.json";
import AREAS from "./__fixtures__/server/work.areas.json";
import OPEN from "./__fixtures__/server/work-order.open.json";
import OPEN_AUDIT from "./__fixtures__/server/work-order.open.audit.json";
import OPEN_CHECKLIST from "./__fixtures__/server/work-order.open.checklist.json";
import OPEN_EDIT from "./__fixtures__/server/work-order.open.edit.json";
import OPEN_CANDIDATES from "./__fixtures__/server/work-order.open.candidates.json";
import HELD from "./__fixtures__/server/work-order.held.json";
import HELD_AUDIT from "./__fixtures__/server/work-order.held.audit.json";
import HELD_CHECKLIST from "./__fixtures__/server/work-order.held.checklist.json";
import DONE from "./__fixtures__/server/work-order.completed.json";
import DONE_AUDIT from "./__fixtures__/server/work-order.completed.audit.json";
import DONE_CHECKLIST from "./__fixtures__/server/work-order.completed.checklist.json";
import DONE_ATTACHMENTS from "./__fixtures__/server/work-order.completed.attachments.json";
import DONE_READINESS from "./__fixtures__/server/work-order.completed.close-readiness.json";
import DONE_SIGNATURE from "./__fixtures__/server/work-order.completed.signature.json";
import ACCEPTED from "./__fixtures__/server/work-order.accepted.json";
import ACCEPTED_AUDIT from "./__fixtures__/server/work-order.accepted.audit.json";
import ACCEPTED_CHECKLIST from "./__fixtures__/server/work-order.accepted.checklist.json";
import ACCEPTED_ATTACHMENTS from "./__fixtures__/server/work-order.accepted.attachments.json";
import ACCEPTED_READINESS from "./__fixtures__/server/work-order.accepted.close-readiness.json";
import ACCEPTED_SIGNATURE from "./__fixtures__/server/work-order.accepted.signature.json";
import CREWS from "./__fixtures__/server/work.crews.technicians.json";
import CREW_DIRECTORY from "./__fixtures__/server/work.crew-directory.json";
import CERT_WATCH from "./__fixtures__/server/work.certification-watch.json";
import TECHNICIAN from "./__fixtures__/server/work.technician.json";
import PARTS from "./__fixtures__/server/work.parts.json";
import PART_ISSUES from "./__fixtures__/server/work.parts.issues.json";
import TEMPLATES from "./__fixtures__/server/work.templates.json";
import TEMPLATE_PACKS from "./__fixtures__/server/work.template-packs.json";
import TEMPLATE from "./__fixtures__/server/work.template.json";
import TEMPLATE_VERSIONS from "./__fixtures__/server/work.template.versions.json";
import TEMPLATE_USAGE from "./__fixtures__/server/work.template.usage.json";
import RULES from "./__fixtures__/server/work.rules.json";
import LABOUR_RATES from "./__fixtures__/server/work.labour-rates.json";
import PERFORMANCE from "./__fixtures__/server/work.performance.json";
import SETTINGS_SLA from "./__fixtures__/server/work.settings.sla.json";
import CUSTOM_FIELDS from "./__fixtures__/server/custom-fields.work-orders.json";

const TENANT = "brazosbend";

type Route_ = { path: string | RegExp; when?: (query: Record<string, unknown>) => boolean; body: unknown };

/** The recorded server, by path. Longest literal wins; an address with no
 *  recording THROWS (and is collected), because a fake that answers `{}` to an
 *  unknown address turns "the screen asked the wrong place" into "the screen
 *  rendered empty" — the very confusion this file exists to remove. */
const ROUTES: Route_[] = [
  { path: "/work-orders/awaiting-approval", body: AWAITING },
  { path: "/work-orders/map", body: MAP },
  { path: "/work-orders", when: (q) => q.status === "complete", body: ORDERS_DONE },
  { path: "/work-orders", body: ORDERS },
  { path: "/work/hold-reasons", body: HOLD_REASONS },
  { path: "/work/raise-options", body: RAISE_OPTIONS },
  { path: "/work/kpis", body: KPIS },
  { path: "/work/areas", body: AREAS },
  { path: "/work/crews", body: CREWS },
  { path: "/work/crew-directory", body: CREW_DIRECTORY },
  { path: "/work/certification-watch", body: CERT_WATCH },
  { path: `/work/technicians/${TECHNICIAN.slug}`, body: TECHNICIAN },
  { path: "/work/parts/issues", body: PART_ISSUES },
  { path: "/work/parts", body: PARTS },
  { path: "/work/template-packs", body: TEMPLATE_PACKS },
  { path: `/work/templates/${TEMPLATE.id}/versions`, body: TEMPLATE_VERSIONS },
  { path: `/work/templates/${TEMPLATE.id}/usage`, body: TEMPLATE_USAGE },
  { path: `/work/templates/${TEMPLATE.id}`, body: TEMPLATE },
  { path: "/work/templates", body: TEMPLATES },
  { path: "/work/rules", body: RULES },
  { path: "/work/labour-rates", body: LABOUR_RATES },
  { path: "/work/performance", body: PERFORMANCE },
  { path: "/work/settings/sla", body: SETTINGS_SLA },
  { path: "/custom-fields", when: (q) => q.entity === "work_orders", body: CUSTOM_FIELDS },
  ...orderRoutes(OPEN.id, { row: OPEN, audit: OPEN_AUDIT, checklist: OPEN_CHECKLIST }),
  { path: `/work-orders/${OPEN.id}/edit`, body: OPEN_EDIT },
  { path: `/work-orders/${OPEN.id}/candidates`, body: OPEN_CANDIDATES },
  ...orderRoutes(HELD.id, { row: HELD, audit: HELD_AUDIT, checklist: HELD_CHECKLIST }),
  ...orderRoutes(DONE.id, { row: DONE, audit: DONE_AUDIT, checklist: DONE_CHECKLIST }),
  { path: `/work-orders/${DONE.id}/attachments`, body: DONE_ATTACHMENTS },
  { path: `/work-orders/${DONE.id}/close-readiness`, body: DONE_READINESS },
  { path: `/work-orders/${DONE.id}/signature`, body: DONE_SIGNATURE },
  ...orderRoutes(ACCEPTED.id, { row: ACCEPTED, audit: ACCEPTED_AUDIT, checklist: ACCEPTED_CHECKLIST }),
  { path: `/work-orders/${ACCEPTED.id}/attachments`, body: ACCEPTED_ATTACHMENTS },
  { path: `/work-orders/${ACCEPTED.id}/close-readiness`, body: ACCEPTED_READINESS },
  { path: `/work-orders/${ACCEPTED.id}/signature`, body: ACCEPTED_SIGNATURE },
];

function orderRoutes(id: string, bodies: { row: unknown; audit: unknown; checklist: unknown }): Route_[] {
  return [
    { path: `/work-orders/${id}/audit`, body: bodies.audit },
    { path: `/work-orders/${id}/checklist`, body: bodies.checklist },
    { path: `/work-orders/${id}`, body: bodies.row },
  ];
}

const unrecorded: string[] = [];

function recordedServer(): ApiClient {
  const get = async (path: string, options?: { query?: Record<string, unknown> }): Promise<ApiResponse<unknown>> => {
    const bare = path.split("?")[0];
    const query = options?.query ?? {};
    const hit = ROUTES.find((r) => (typeof r.path === "string" ? r.path === bare : r.path.test(bare)) && (r.when ? r.when(query) : true));
    if (hit === undefined) {
      unrecorded.push(`GET ${bare}`);
      throw new Error(`no recording for GET ${bare}`);
    }
    return { status: 200, data: hit.body, etag: null, notModified: false };
  };
  const write = async () => ({ status: 200, data: {}, etag: null, notModified: false });
  return { get, post: write, put: write, patch: write, delete: write, del: write } as unknown as ApiClient;
}

function mount(path: string, pattern: string, element: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        {/* Mounted under the REAL path pattern, never bare (`DEF-CWP-3925`). */}
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path={pattern} element={element} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function arrived(text: string | RegExp) {
  expect((await screen.findAllByText(text, undefined, { timeout: 4000 })).length).toBeGreaterThan(0);
  expect(document.querySelector("[data-not-built-yet]")).toBeNull();
}

afterEach(() => {
  cleanup();
  unrecorded.length = 0;
});

describe("the recordings are the server's own shapes (read once, here, not typed)", () => {
  it("covers the three cases that have broken the order page: a unit, a hold, a signature", () => {
    expect(OPEN.location?.unit?.label).toBeTruthy();
    expect(HELD.dispatch_state).toBe("on_hold");
    expect(HELD.hold?.reason?.name).toBeTruthy();
    expect(DONE.shape).toBe("completed");
    expect(DONE.signature?.printed_name).toBeTruthy();
    expect(ACCEPTED.accepted?.by?.name).toBeTruthy();
  });
});

describe("Orders (1·1) and Approvals (2·1) draw the recorded rows", () => {
  it("Orders draws every recorded order number", async () => {
    mount(`/${TENANT}/work/orders`, "/:tenant/work/orders", <OrdersPage client={recordedServer()} />);
    await arrived(ORDERS.results[0].order_no);
    for (const row of ORDERS.results.slice(0, 10)) {
      expect(screen.getAllByText(row.order_no).length).toBeGreaterThan(0);
    }
  });

  it("Approvals draws every recorded order waiting", async () => {
    mount(
      `/${TENANT}/work/awaiting-approval`,
      "/:tenant/work/awaiting-approval",
      <AwaitingApprovalPage client={recordedServer()} />,
    );
    await arrived(AWAITING.results[0].order_no);
    for (const row of AWAITING.results) {
      expect(screen.getAllByText(row.order_no).length).toBeGreaterThan(0);
    }
  });
});

describe("one order (1·2) — the three recorded shapes open, none crashes", () => {
  const at = (id: string, tab: string) => `/${TENANT}/work/orders/${id}?tab=${tab}`;
  const pattern = "/:tenant/work/orders/:orderNo";

  it("an OPEN job at a unit names the unit (DEF-WRK-9600 crashed here)", async () => {
    mount(at(OPEN.id, "overview"), pattern, <OrderDetailPage client={recordedServer()} />);
    await arrived(OPEN.location.unit.label);
    expect(screen.getAllByText(new RegExp(OPEN.order_no)).length).toBeGreaterThan(0);
  });

  it("an OPEN job's checklist draws the recorded tasks", async () => {
    mount(at(OPEN.id, "checklist"), pattern, <OrderDetailPage client={recordedServer()} />);
    await arrived(OPEN_CHECKLIST.tasks[0].title);
  });

  it("an OPEN job's history draws one line per recorded row", async () => {
    mount(at(OPEN.id, "audit"), pattern, <OrderDetailPage client={recordedServer()} />);
    await arrived(new RegExp(OPEN.order_no));
    const names = OPEN_AUDIT.results.map((r) => r.who?.name).filter((n): n is string => Boolean(n));
    expect(names.length).toBeGreaterThan(0);
    expect((await screen.findAllByText(new RegExp(names[0]))).length).toBeGreaterThan(0);
  });

  it("a HELD job names its recorded reason", async () => {
    mount(at(HELD.id, "overview"), pattern, <OrderDetailPage client={recordedServer()} />);
    await arrived(new RegExp(HELD.order_no));
    expect((await screen.findAllByText(new RegExp(HELD.hold.reason.name))).length).toBeGreaterThan(0);
  });

  it("a COMPLETED job shows who signed and who closed it", async () => {
    mount(at(DONE.id, "overview"), pattern, <OrderDetailPage client={recordedServer()} />);
    await arrived(new RegExp(DONE.order_no));
    expect((await screen.findAllByText(new RegExp(DONE.signature.printed_name))).length).toBeGreaterThan(0);
    expect((await screen.findAllByText(new RegExp(DONE.closed.by.name))).length).toBeGreaterThan(0);
  });

  it("an ACCEPTED job (accepted {by {name}}, no signature) opens and offers no Accept", async () => {
    // The presence first, so the absence below cannot pass over a page that
    // simply never draws the button: the completed, NOT accepted job offers it.
    mount(at(DONE.id, "overview"), pattern, <OrderDetailPage client={recordedServer()} />);
    await arrived(new RegExp(DONE.order_no));
    expect(screen.getAllByRole("button", { name: /^Accept/ }).length).toBeGreaterThan(0);
    cleanup();
    mount(at(ACCEPTED.id, "overview"), pattern, <OrderDetailPage client={recordedServer()} />);
    await arrived(new RegExp(ACCEPTED.order_no));
    expect(screen.queryByRole("button", { name: /^Accept/ })).toBeNull();
  });

  it("no order page asked an address with no recording", async () => {
    const all = [OPEN, HELD, DONE, ACCEPTED];
    for (const id of all.map((o) => o.id)) {
      for (const tab of ["overview", "checklist", "parts", "audit"]) {
        mount(at(id, tab), pattern, <OrderDetailPage client={recordedServer()} />);
        await screen.findAllByText(new RegExp(all.find((o) => o.id === id)!.order_no));
        cleanup();
      }
    }
    expect(unrecorded).toEqual([]);
  });
});

describe("Put on hold (image 10) offers every recorded reason (DEF-WRK-9601 offered none)", () => {
  it("listHoldReasons keeps every row the server sent, in rank order", async () => {
    const reasons = await listHoldReasons(recordedServer());
    const recorded = Array.isArray(HOLD_REASONS) ? HOLD_REASONS : HOLD_REASONS.results;
    expect(reasons.map((r) => r.name)).toEqual(
      [...recorded].sort((a, b) => a.rank - b.rank).map((r) => r.name),
    );
    expect(reasons.length).toBeGreaterThan(0);
  });
});

describe("the edit page (1·3) opens on the recorded form", () => {
  it("names the order and its recorded holder", async () => {
    mount(
      `/${TENANT}/work/orders/${OPEN.id}/edit`,
      "/:tenant/work/orders/:orderId/edit",
      <OrderEditPage client={recordedServer()} />,
    );
    await arrived(new RegExp(OPEN_EDIT.order_no));
    expect((await screen.findAllByText(new RegExp(OPEN_EDIT.technician.name))).length).toBeGreaterThan(0);
  });
});

describe("Map (3·1) draws a mark for the recorded pins", () => {
  it("every recorded pin is somewhere on the map", async () => {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <MemoryRouter initialEntries={[`/${TENANT}/work/map`]}>
          <Routes>
            <Route path="/:tenant/work/map" element={<MapView onOpen={() => undefined} client={recordedServer()} />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const marks = await screen.findAllByRole("button", { name: /WO-|job/i }, { timeout: 4000 });
    expect(marks.length).toBeGreaterThan(0);
    expect(MAP.pins.length + MAP.unplaced.length).toBe(MAP.total);
  });
});

describe("Crews (4·1), one technician (4·2), Parts (5·1)", () => {
  it("Crews draws every recorded name", async () => {
    mount(`/${TENANT}/work/crews`, "/:tenant/work/crews", <CrewsPage client={recordedServer()} />);
    await arrived(CREWS.results[0].name);
    for (const row of CREWS.results) expect(screen.getAllByText(row.name).length).toBeGreaterThan(0);
  });

  it("one technician opens on the recorded person", async () => {
    mount(
      `/${TENANT}/work/crews/${TECHNICIAN.slug}`,
      "/:tenant/work/crews/:slug",
      <TechnicianDetailPage client={recordedServer()} />,
    );
    await arrived(TECHNICIAN.name);
    const held = TECHNICIAN.skills.find((s) => s.proficiency !== "not_held");
    if (held) expect(screen.getAllByText(new RegExp(held.name)).length).toBeGreaterThan(0);
  });

  it("Parts draws every recorded part number", async () => {
    mount(`/${TENANT}/work/parts`, "/:tenant/work/parts", <PartsPage client={recordedServer()} />);
    await arrived(PARTS.results[0].part_no);
    for (const row of PARTS.results) expect(screen.getAllByText(row.part_no).length).toBeGreaterThan(0);
  });
});

describe("Templates (6·1–6·2) and Performance (8·1)", () => {
  it("Templates draws every recorded template", async () => {
    mount(`/${TENANT}/work/templates`, "/:tenant/work/templates", <TemplatesPage client={recordedServer()} />);
    await arrived(TEMPLATES.results[0].name);
    for (const row of TEMPLATES.results) expect(screen.getAllByText(row.name).length).toBeGreaterThan(0);
  });

  it("one template opens on the recorded template", async () => {
    mount(
      `/${TENANT}/work/templates/${TEMPLATE.id}`,
      "/:tenant/work/templates/:templateId",
      <TemplateDetailPage client={recordedServer()} />,
    );
    await arrived(TEMPLATE.name);
  });

  it("Performance draws one row per recorded job type", async () => {
    mount(`/${TENANT}/work/performance`, "/:tenant/work/performance", <PerformancePage client={recordedServer()} />);
    await arrived(PERFORMANCE.results[0].job_type);
    const table = screen.getAllByRole("table")[0];
    for (const row of PERFORMANCE.results) {
      expect(within(table).getAllByText(row.job_type).length).toBeGreaterThan(0);
    }
  });
});
