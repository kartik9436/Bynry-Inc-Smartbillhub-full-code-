// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    CR-168-BRC10 round 2, lane ORDERS-LIST — Orders (image 01, 02), the
//           edit page (images 12, 13), Approvals (images 21, 22, 23)
// Tasks:    P1.1 · P1.3 · P1.4 · P1.5 · P1.7 · P1.13 · P1.26 · P1.27 (edit
//           page) · P1.30 (edit page, list) · P1.36 · P2.1 · P3.7
// Defects:  DEF-WRK-9562 · DEF-WRK-9563 · DEF-WRK-9570 · DEF-WRK-9575 ·
//           DEF-WRK-4105 — each case below was run on the tip BEFORE the fix
//           and its failure is quoted in the lane's report
// Rules:    ruling 1 (the tab is Approvals) · ruling 16 (actions top right,
//           B14 rule 2) · ruling 18 (the office only accepts) · BR-MET-110
//           (a person accepts what the field sent) · B14 rules 15, 31, 33
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY SCREEN HERE IS MOUNTED UNDER ITS REAL PATH PATTERN** (hard-won
// law 2's fixture clause): a bare `MemoryRouter` leaves `:tenant` undefined and
// every address the page builds reads `//work/…`, which `toContain` accepts.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { resolveScreen } from "@/routing/screenIds";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { AwaitingApprovalPage } from "./AwaitingApprovalPage";
import { OrderEditPage } from "./OrderEditPage";
import { OrdersPage } from "./OrdersPage";
import type {
  AwaitingApprovalRow,
  OrderEditForm,
  WorkKpis,
  WorkOrderDispatchRow,
} from "./workEndpoints";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(() => cleanup());

type Call = { method: string; path: string; body: unknown };
const ok = (data: unknown) => ({ status: 200, data, etag: null, notModified: false }) as ApiResponse<unknown>;
const EMPTY = { count: 0, next: null, previous: null, results: [] };

/** A client that answers each path with its own shape, records every write,
 *  and refuses a write whose path ends with `fail` with the server's own 404. */
function fakeClient(
  calls: Call[],
  reads: Record<string, unknown>,
  opts: { fail?: string; post?: (path: string) => unknown } = {},
): ApiClient {
  const write = (method: string) => async (path: string, body?: unknown) => {
    calls.push({ method, path, body: body ?? null });
    if (opts.fail !== undefined && path.endsWith(opts.fail)) {
      throw new ApiError(404, { code: "NOT_FOUND", message_key: "errors.not-found" } as never);
    }
    return ok(opts.post ? opts.post(path) : {});
  };
  return {
    get: async (path: string) => {
      calls.push({ method: "GET", path, body: null });
      if (path in reads) return ok(reads[path]);
      if (path.startsWith("/lookups/")) return ok(EMPTY);
      if (path.startsWith("/custom-fields")) return ok({ results: [] });
      throw new Error(`unexpected read: ${path}`);
    },
    post: write("POST"),
    patch: write("PATCH"),
    put: write("PUT"),
    del: write("DELETE"),
    request: write("REQUEST"),
  } as unknown as ApiClient;
}

function freshClient(): QueryClient {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.customFieldRegistry("work_orders", "WORK_EDIT", "input"), []);
  return queryClient;
}

/** CR-168 round 3 (lane ASSIGN): *Assigned to* is image 12's search picker,
 *  not a `<select>` — a candidate is chosen by opening the list and pressing
 *  the name, the way a dispatcher does. */
function pickHolder(name: string) {
  const box = screen.getByRole("combobox", { name: new RegExp(t("work.edit.field.assignedTo")) });
  fireEvent.focus(box);
  const option = Array.from(document.querySelectorAll<HTMLElement>('[role="option"]')).find(
    (el) => el.querySelector(".font-semibold")?.textContent === name,
  );
  if (!option) throw new Error(`${name} is not offered`);
  fireEvent.click(option);
}

async function settled(queryClient: QueryClient, text: string) {
  await waitFor(() => {
    if (queryClient.isFetching() !== 0) throw new Error("still fetching");
    if (screen.queryAllByText(text).length === 0) throw new Error(`${text} not in yet`);
  });
}

// ══════════════════════════════════════════════════════════════════════════
// The edit page — images 12 (assign) and 13 (reassign)
// ══════════════════════════════════════════════════════════════════════════

const ORDER_ID = "6f1c2b9e-0040-4000-8000-000000000040";

function editForm(over: Partial<OrderEditForm> = {}): OrderEditForm {
  return {
    id: ORDER_ID,
    order_no: "WO-0040",
    type: "Meter exchange — residential",
    dispatch_state: "queued",
    state: "planned",
    priority_id: "pr-normal",
    due_at: null,
    window_start: null,
    window_end: null,
    area_id: null,
    technician_notes: null,
    custom_data: {},
    technician: null,
    technician_id: null,
    premise: { id: "p-1", premise_no: "P-00101", address: "101 Silver Creek Rd" },
    template_id: null,
    priority_locked: false,
    ...over,
  };
}

// §7.3's envelope, as SRV-2 serves it (2.500.0) — the old `{skill, policy,
// candidates[]}` is read by nothing since lane ASSIGN (round 3).
const ADVICE = {
  skill: null,
  has_skill: true,
  area_match: false,
  off_that_day: false,
  jobs_that_day: 0,
  certifications_lapsed: [],
};
const CANDIDATES = {
  count: 4,
  next: null,
  previous: null,
  results: [
    { kind: "person", id: "tech-patel", name: "R. Patel", advice: ADVICE, best_fit: false },
    { kind: "person", id: "tech-ortiz", name: "D. Ortiz", advice: ADVICE, best_fit: false },
    { kind: "crew", id: "crew-b", name: "Field crew B", advice: ADVICE, best_fit: false },
    { kind: "contractor", id: "con-redline", name: "Redline Meter Services", advice: ADVICE, best_fit: false },
  ],
};

function mountEdit(form: OrderEditForm, calls: Call[], opts: { fail?: string } = {}) {
  const client = fakeClient(
    calls,
    {
      [`/work-orders/${ORDER_ID}/edit`]: form,
      [`/work-orders/${ORDER_ID}/candidates`]: CANDIDATES,
      "/work/areas": { results: [{ id: "ar-nw", code: "NW", name: "NW" }] },
      "/work/kpis": KPIS,
      "/work-orders": { ...EMPTY },
      "/work/crews": { ...EMPTY, counts: { rows: 0, people: 0, crews: 0, contractors: 0 } },
    },
    opts,
  );
  const queryClient = freshClient();
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/work/orders/${ORDER_ID}/edit`]}>
          <Routes>
            <Route path="/:tenant/work/orders/:orderId/edit" element={<OrderEditPage client={client} />} />
            <Route path="/:tenant/work/orders" element={<p>the orders list</p>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return queryClient;
}

const ASSIGNED_TO_ORTIZ = editForm({
  order_no: "WO-0043",
  dispatch_state: "scheduled",
  technician: { kind: "person", name: "D. Ortiz", slug: "d-ortiz" },
  technician_id: "tech-ortiz",
});

describe("DEF-WRK-9563 — a crew or a contractor picked on the edit page is ASSIGNED, or says why not", () => {
  it("picking a CREW posts crew_id, never the crew's id as a technician_id", async () => {
    const calls: Call[] = [];
    const queryClient = mountEdit(editForm(), calls);
    await settled(queryClient, "Field crew B");
    pickHolder("Field crew B");
    await userEvent.click(screen.getByRole("button", { name: /Assign ✓/ }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PATCH")).toHaveLength(1));
    const body = calls.find((c) => c.method === "PATCH")?.body as Record<string, unknown>;
    expect(body.crew_id).toBe("crew-b");
    expect(body.technician_id ?? null).toBeNull();
  });

  it("picking a CONTRACTOR posts crew_id too — a contractor is a crew row", async () => {
    const calls: Call[] = [];
    const queryClient = mountEdit(editForm(), calls);
    await settled(queryClient, "Redline Meter Services");
    pickHolder("Redline Meter Services");
    await userEvent.click(screen.getByRole("button", { name: /Assign ✓/ }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PATCH")).toHaveLength(1));
    const body = calls.find((c) => c.method === "PATCH")?.body as Record<string, unknown>;
    expect(body.crew_id).toBe("con-redline");
  });

  it("P1.1 — a refused save SAYS SO on the page and stays on it", async () => {
    const calls: Call[] = [];
    const queryClient = mountEdit(editForm(), calls, { fail: ORDER_ID });
    await settled(queryClient, "R. Patel");
    pickHolder("R. Patel");
    await userEvent.click(screen.getByRole("button", { name: /Assign ✓/ }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("errors.not-found"));
    expect(screen.queryByText("the orders list")).toBeNull();
  });

  it("P1.1 — a refused CANCEL says so too", async () => {
    const calls: Call[] = [];
    const queryClient = mountEdit(editForm(), calls, { fail: "/cancel" });
    await settled(queryClient, "R. Patel");
    await userEvent.click(screen.getByRole("button", { name: t("work.edit.action.cancelOrder") }));
    await userEvent.click(await screen.findByRole("button", { name: t("work.edit.confirm.confirm") }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(t("errors.not-found"));
  });
});

describe("images 12 and 13 — the edit page's head, its words and its effects", () => {
  it("P1.30 / ruling 16 — Cancel, Cancel work order and the commit sit in the PAGE HEADER", async () => {
    const calls: Call[] = [];
    const queryClient = mountEdit(editForm(), calls);
    await settled(queryClient, "R. Patel");
    const head = document.querySelector(".page-header-actions") as HTMLElement;
    expect(head).not.toBeNull();
    const words = within(head)
      .getAllByRole("button")
      .map((button) => button.textContent?.trim());
    expect(words).toEqual(["Cancel", "Cancel work order", "Assign ✓"]);
  });

  it("P1.27 — a job somebody holds reads Reassign ✓ and opens on its holder", async () => {
    const calls: Call[] = [];
    const queryClient = mountEdit(ASSIGNED_TO_ORTIZ, calls);
    await settled(queryClient, "D. Ortiz");
    expect(screen.getByRole("button", { name: /Reassign ✓/ })).toBeDefined();
    const picker = screen.getByRole("combobox", { name: new RegExp(t("work.edit.field.assignedTo")) }) as HTMLInputElement;
    expect(picker.value).toBe("D. Ortiz");
  });

  it("DEF-WRK-9530's gap — a CREW-held job opens on its crew, whose list name carries a head-count", async () => {
    const calls: Call[] = [];
    const crewHeld = editForm({
      dispatch_state: "scheduled",
      technician: { kind: "crew", name: "Field crew B", slug: "field-crew-b" },
      technician_id: null,
    });
    const client = CANDIDATES.results.map((c) => (c.id === "crew-b" ? { ...c, name: "Field crew B (2)" } : c));
    const original = CANDIDATES.results;
    CANDIDATES.results = client;
    try {
      const queryClient = mountEdit(crewHeld, calls);
      await settled(queryClient, "Field crew B (2)");
      const picker = screen.getByRole("combobox", { name: new RegExp(t("work.edit.field.assignedTo")) }) as HTMLInputElement;
      await waitFor(() => expect(picker.value).toBe("Field crew B (2)"));
      expect(screen.getByRole("button", { name: /Reassign ✓/ })).toBeDefined();
    } finally {
      CANDIDATES.results = original;
    }
  });

  it("ruling 18 — the office cannot pick Complete as a status", async () => {
    const calls: Call[] = [];
    const queryClient = mountEdit(editForm(), calls);
    await settled(queryClient, "R. Patel");
    const status = document.querySelector('[data-field="dispatch_state"]') as HTMLSelectElement;
    const values = Array.from(status.options).map((option) => option.value);
    expect(values).not.toContain("complete");
    expect(values).toEqual(["queued", "scheduled", "en_route", "on_site", "on_hold", "cancelled"]);
  });

  it("P1.26 — a priority-only change promises the customer nothing", async () => {
    const calls: Call[] = [];
    const queryClient = mountEdit(ASSIGNED_TO_ORTIZ, calls);
    await settled(queryClient, "D. Ortiz");
    const box = document.querySelector('[data-consequence="change-effects"]') as HTMLElement;
    expect(box.textContent).toContain(t("work.edit.effects.customerNotTold"));
    expect(box.textContent).not.toContain(t("work.edit.effects.customerMoved"));
  });

  it("P1.26 — a reassign names BOTH people, and a moved day tells the customer", async () => {
    const calls: Call[] = [];
    const queryClient = mountEdit(ASSIGNED_TO_ORTIZ, calls);
    await settled(queryClient, "R. Patel");
    pickHolder("R. Patel");
    const box = document.querySelector('[data-consequence="change-effects"]') as HTMLElement;
    expect(box.textContent).toContain(t("work.edit.effects.offThem", { name: "D. Ortiz" }));
    expect(box.textContent).toContain(t("work.edit.effects.toldNow", { name: "R. Patel" }));
    expect(box.textContent).toContain(t("work.edit.effects.customerNotTold"));
    await userEvent.type(screen.getByLabelText(new RegExp(`^${t("work.edit.field.date")}`, "u")), "2026-09-25");
    expect(box.textContent).toContain(t("work.edit.effects.customerMoved"));
  });

  it("image 12 — Date has a Today button that fills it", async () => {
    const calls: Call[] = [];
    const queryClient = mountEdit(editForm(), calls);
    await settled(queryClient, "R. Patel");
    await userEvent.click(screen.getByRole("button", { name: t("forms.date.today") }));
    const date = screen.getByLabelText(new RegExp(`^${t("work.edit.field.date")}`, "u")) as HTMLInputElement;
    expect(date.value).toMatch(/^\d{4}-\d{2}-\d{2}$/u);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Orders — images 01 and 02
// ══════════════════════════════════════════════════════════════════════════

const KPIS: WorkKpis = {
  open_total: 2,
  unassigned: { count: 1 },
  due_today: { count: 0, urgent: 0 },
  in_field: { count: 0 },
  awaiting_approval: { count: 0 },
  overdue: { count: 0, worst: null },
};

function dispatchRow(over: Partial<WorkOrderDispatchRow> = {}): WorkOrderDispatchRow {
  return {
    id: "wo-0043",
    order_no: "WO-0043",
    type: "Meter exchange — residential",
    premise: { id: "p-1", premise_no: "P-00101", address: "101 Silver Creek Rd" },
    service: "water",
    state: "planned",
    outcome: null,
    mode: "our_crew",
    is_gate: false,
    connection: null,
    account: null,
    raised_at: "2026-09-24T12:00:00Z",
    priority: null,
    technician: null,
    due_at: null,
    window_start: null,
    window_end: null,
    dispatch_state: "queued",
    source: "dispatcher",
    source_ref: null,
    area: null,
    ...over,
  };
}

function mountOrders(calls: Call[], opts: { fail?: string } = {}) {
  const rows = [dispatchRow(), dispatchRow({ id: "wo-0040", order_no: "WO-0040" })];
  const client = fakeClient(
    calls,
    {
      "/work/kpis": KPIS,
      "/work/areas": { results: [] },
      "/work/crews": { ...EMPTY, counts: { rows: 0, people: 0, crews: 0, contractors: 0 } },
      "/work-orders": { count: 2, next: null, previous: null, results: rows },
      "/work-orders/wo-0043/candidates": CANDIDATES,
      "/work-orders/wo-0040/candidates": CANDIDATES,
    },
    opts,
  );
  const queryClient = freshClient();
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/work/orders`]}>
          <Routes>
            <Route path="/:tenant/work/orders" element={<OrdersPage client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return queryClient;
}

async function tickBoth(queryClient: QueryClient) {
  await settled(queryClient, "WO-0040");
  await userEvent.click(await screen.findByLabelText("Select WO-0043"));
  await userEvent.click(await screen.findByLabelText("Select WO-0040"));
}

describe("DEF-WRK-9562 / DEF-WRK-4105 / P2.1 — + New work order is the page's primary act, top right", () => {
  it("sits in the PAGE HEADER over a populated list, accent tier, and opens the raise", async () => {
    const calls: Call[] = [];
    const queryClient = mountOrders(calls);
    await settled(queryClient, "WO-0040");
    const head = document.querySelector(".page-header-actions") as HTMLElement;
    const create = within(head).getByRole("link", { name: "+ New work order" });
    expect(create.getAttribute("href")).toBe(`/${TENANT}/work/orders/new`);
    expect(create.className).toMatch(/(^|\s)bg-accent(\s|$)/u);
    // ONE create on the screen: the old row under the pager is gone.
    expect(document.querySelector("[data-orders-actions]")).toBeNull();
  });
});

describe("DEF-WRK-9570 / P1.4 — reschedule takes a real date and a window, never free text", () => {
  it("Reschedule offers a date picker and the three windows, and posts real moments", async () => {
    const calls: Call[] = [];
    const queryClient = mountOrders(calls);
    await tickBoth(queryClient);
    await userEvent.click(screen.getByRole("button", { name: "Reschedule selected…" }));
    const dialog = await screen.findByRole("dialog");
    const date = within(dialog).getByLabelText(new RegExp(`^${t("work.orders.bulk.when")}`, "u")) as HTMLInputElement;
    expect(date.type).toBe("date");
    const windowPicker = within(dialog).getByLabelText(t("work.orders.bulk.window")) as HTMLSelectElement;
    expect(windowPicker.tagName).toBe("SELECT");
    expect(within(dialog).queryByLabelText("Window opens")).toBeNull();
    await userEvent.type(date, "2026-09-25");
    await userEvent.selectOptions(windowPicker, "morning");
    await userEvent.click(within(dialog).getByRole("button", { name: t("work.orders.bulk.submit.reschedule") }));
    await waitFor(() => expect(calls.filter((c) => c.method === "POST")).toHaveLength(1));
    const body = calls.find((c) => c.method === "POST")?.body as Record<string, unknown>;
    expect(body).toMatchObject({
      act: "reschedule",
      scheduled_for: "2026-09-25T00:00:00",
      window_start: "2026-09-25T08:00:00",
      window_end: "2026-09-25T12:00:00",
    });
  });

  it("P1.1 — a refused bulk act shows the server's sentence in the dialog", async () => {
    const calls: Call[] = [];
    const queryClient = mountOrders(calls, { fail: "/work-orders/bulk" });
    await tickBoth(queryClient);
    await userEvent.click(screen.getByRole("button", { name: "Reschedule selected…" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText(new RegExp(`^${t("work.orders.bulk.when")}`, "u")), "2026-09-25");
    await userEvent.click(within(dialog).getByRole("button", { name: t("work.orders.bulk.submit.reschedule") }));
    expect(await within(dialog).findByText(t("errors.not-found"))).toBeDefined();
  });

  it("image 02 — Assign 2 orders asks who, the date and the window", async () => {
    const calls: Call[] = [];
    const queryClient = mountOrders(calls);
    await tickBoth(queryClient);
    await userEvent.click(screen.getByRole("button", { name: "Assign selected…" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Assign 2 orders")).toBeDefined();
    expect((within(dialog).getByLabelText(new RegExp(`^${t("work.orders.bulk.when")}`, "u")) as HTMLInputElement).type).toBe("date");
    expect(within(dialog).getByLabelText(t("work.orders.bulk.window")).tagName).toBe("SELECT");
    expect(within(dialog).getByText(t("work.orders.bulk.toldOnPhone"))).toBeDefined();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// Approvals — images 21, 22, 23
// ══════════════════════════════════════════════════════════════════════════

function approvalRow(over: Partial<AwaitingApprovalRow> = {}): AwaitingApprovalRow {
  return {
    id: "wo-0043",
    order_no: "WO-0043",
    type: "Meter exchange — residential",
    premise: { id: "p-1", premise_no: "P-00101", address: "101 Silver Creek Rd" },
    service: "water",
    outcome: "passed",
    completed_at: "2026-09-24T09:00:00Z",
    waiting_days: 3,
    connection: { id: "con-1", connection_no: "C-00001", home: { kind: "premises", id: "p-1" } },
    ...over,
  };
}

const NO_BUILD = approvalRow({
  id: "wo-0021",
  order_no: "WO-0021",
  type: "Meter set",
  premise: { id: "p-2", premise_no: "P-00102", address: "Kestrel Park ph. 2" },
  service: "electric",
  outcome: "partially_done",
  connection: null,
  waiting_days: 2,
});

function Landed() {
  return <p data-testid="landed">{useLocation().pathname}</p>;
}

function mountApprovals(
  rows: AwaitingApprovalRow[],
  calls: Call[],
  opts: { fail?: string; probeOrders?: boolean } = {},
) {
  let queue = [...rows];
  const client = fakeClient(calls, {}, { ...opts, post: () => ({ accepted: true }) });
  const base = client.get;
  (client as unknown as { get: unknown }).get = async (path: string) => {
    if (path === "/work-orders/awaiting-approval") {
      calls.push({ method: "GET", path, body: null });
      return ok({ count: queue.length, next: null, previous: null, results: queue, oldest_waiting: 3 });
    }
    return base(path);
  };
  const post = client.post;
  (client as unknown as { post: unknown }).post = async (path: string, body?: unknown) => {
    const answer = await post(path, body);
    queue = queue.filter((row) => path !== `/work-orders/${row.id}/accept`);
    return answer;
  };
  const queryClient = freshClient();
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/work/awaiting-approval`]}>
          <Routes>
            <Route path="/:tenant/work/awaiting-approval" element={<AwaitingApprovalPage client={client} />} />
            {opts.probeOrders ? <Route path="/:tenant/work/orders" element={<Landed />} /> : null}
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return queryClient;
}

describe("ruling 1 / P1.13 — the tab and the title read Approvals", () => {
  it("in English, and in every catalogue a value of its own", () => {
    expect(t("work.tabs.approvals")).toBe("Approvals");
    expect(t("work.approvals.title")).toBe("Approvals");
    for (const lang of ["de", "es", "es-MX", "fr-FR", "hi", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"]) {
      const word = i18n.getFixedT(lang)("work.tabs.approvals");
      expect(word, lang).not.toBe("Approvals");
      expect(word, lang).not.toMatch(/approval/iu);
    }
  });
});

describe("DEF-WRK-9575 / P1.5 / P1.7 — every row opens its ORDER, and the empty queue's door is live", () => {
  it("the eye opens /work/orders/{id}, with or without a build", async () => {
    const calls: Call[] = [];
    const queryClient = mountApprovals([approvalRow(), NO_BUILD], calls);
    await settled(queryClient, "WO-0021");
    const eyes = screen.getAllByRole("link", { name: t("work.approvals.open") });
    expect(eyes.map((eye) => eye.getAttribute("href"))).toEqual([
      `/${TENANT}/work/orders/wo-0043`,
      `/${TENANT}/work/orders/wo-0021`,
    ]);
  });

  it("an empty queue's Open work orders goes to the Orders list", async () => {
    // ⚠ P3.20 — THIS CASE WAS NAMED AFTER AN ASSERTION IT DID NOT MAKE (law 7,
    // *looking at the wrong thing*): it proved the button enabled and never
    // where it went. It now presses it and reads the address it LANDS on and
    // the screen that address opens.
    const calls: Call[] = [];
    const queryClient = mountApprovals([], calls, { probeOrders: true });
    await settled(queryClient, t("work.approvals.empty.cta"));
    expect(screen.queryByText(t("work.approvals.empty.ctaReason"))).toBeNull();
    const cta = screen.getByRole("button", { name: t("work.approvals.empty.cta") }) as HTMLButtonElement;
    expect(cta.disabled).toBe(false);
    await userEvent.click(cta);
    const landed = (await screen.findByTestId("landed")).textContent ?? "";
    expect(landed).toBe(`/${TENANT}/work/orders`);
    expect(resolveScreen(landed).r10).toBe("WRK-01");
  });

  it("P3.20 — the eye's address opens the ORDER page (WRK-02), not the premises", async () => {
    const calls: Call[] = [];
    const queryClient = mountApprovals([approvalRow()], calls);
    await settled(queryClient, "WO-0043");
    const eye = screen.getByRole("link", { name: t("work.approvals.open") });
    expect(resolveScreen(eye.getAttribute("href") ?? "").r10).toBe("WRK-02");
  });
});

describe("P1.36 / P3.7 — the supervisor accepts from the queue (images 22, 23)", () => {
  it("✓ on a row asks first, naming the consequence, then accepts that one order", async () => {
    const calls: Call[] = [];
    const queryClient = mountApprovals([approvalRow(), NO_BUILD], calls);
    await settled(queryClient, "WO-0043");
    await userEvent.click(screen.getByRole("button", { name: t("work.approvals.accept", { order: "WO-0043" }) }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText("Accept WO-0043?")).toBeDefined();
    expect(dialog.textContent).toContain(t("work.approvals.acceptConsequence"));
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
    await userEvent.click(within(dialog).getByRole("button", { name: "Accept ✓" }));
    await waitFor(() =>
      expect(calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual([
        "/work-orders/wo-0043/accept",
      ]),
    );
    expect(await screen.findByText("WO-0043 accepted · service live")).toBeDefined();
  });

  it("DEF-WRK-9679 — the question names who closed the job (image 22), and says nothing when nobody is recorded", async () => {
    const calls: Call[] = [];
    const queryClient = mountApprovals(
      [approvalRow({ closed_by: { name: "D. Ortiz" } }), { ...NO_BUILD, closed_by: null }],
      calls,
    );
    await settled(queryClient, "WO-0043");
    await userEvent.click(screen.getByRole("button", { name: t("work.approvals.accept", { order: "WO-0043" }) }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog.textContent).toContain(
      `101 Silver Creek Rd · ${t("work.orders.service.water")} · ${t("work.approvals.closedBy", { name: "D. Ortiz" })}`,
    );
    await userEvent.click(within(dialog).getByRole("button", { name: t("work.approvals.keepWaiting") }));
    await userEvent.click(screen.getByRole("button", { name: t("work.approvals.accept", { order: "WO-0021" }) }));
    const second = await screen.findByRole("alertdialog");
    expect(second.textContent).not.toContain(t("work.approvals.closedBy", { name: "" }).trim());
  });

  it("Keep waiting closes the question and accepts nothing", async () => {
    const calls: Call[] = [];
    const queryClient = mountApprovals([approvalRow()], calls);
    await settled(queryClient, "WO-0043");
    await userEvent.click(screen.getByRole("button", { name: t("work.approvals.accept", { order: "WO-0043" }) }));
    await userEvent.click(await screen.findByRole("button", { name: "Keep waiting" }));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
  });

  it("ticking two rows puts Accept selected… (2) top right, and accepts each with its own answer", async () => {
    const calls: Call[] = [];
    const queryClient = mountApprovals([approvalRow(), NO_BUILD], calls, { fail: "wo-0021/accept" });
    await settled(queryClient, "WO-0021");
    await userEvent.click(screen.getByLabelText("Select WO-0043"));
    await userEvent.click(screen.getByLabelText("Select WO-0021"));
    const head = document.querySelector(".page-header-actions") as HTMLElement;
    await userEvent.click(within(head).getByRole("button", { name: "Accept selected… (2)" }));
    const dialog = await screen.findByRole("alertdialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Accept ✓" }));
    await waitFor(() =>
      expect(calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual([
        "/work-orders/wo-0043/accept",
        "/work-orders/wo-0021/accept",
      ]),
    );
    expect(await screen.findByText(t("work.approvals.acceptedSome", { done: 1, failed: 1 }))).toBeDefined();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-168-BRC10 §5.1, §5.2, §5.4, §8 R2 ORDERS-LIST · images 01, 02, 12, 13, 21, 22, 23
// generated: 2026-10-04 by lane ORDERS-LIST (CR-168-BRC10 round 2)
// gates: RED PROVED FIRST on the tip — every describe above failed before its fix (quoted in the lane report)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
