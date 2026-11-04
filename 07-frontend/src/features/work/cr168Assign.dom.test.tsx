// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Story:    CR-168-BRC10 round 3, lane ASSIGN — the advice beside every name
//           (images 12, 13), bulk assign (image 02), technician acceptance on
//           the list and the order (P4.1), the order page's Assign… (P1.27)
// Tasks:    P4.1 · P4.12 · P4.13 · P1.27 (order-page half) · P4.4 (the
//           screen half: Why it moves)
// Rules:    ruling 2 (PO 2026-09-23 / answer 2, 2026-10-04 — the skill match
//           ADVISES and never blocks; a lapsed certificate only WARNS;
//           BR-WRK-029 and BR-WRK-030 superseded) · NFR-3 / NFR-5 (the
//           candidates are paged and searched, never capped) · B14 rules 31,
//           33, 37, 42, 44
// ───────────────────────────────────────────────────────
//
// Every screen is mounted under its REAL path pattern (hard-won law 2's
// fixture clause). The candidates arrive in §7.3's shape — `{results, count,
// next, previous}`, each row with `advice` and `best_fit` — and one case keeps
// today's `{skill, policy, candidates[]}` so the screen reads both while lane
// SRV-2's server lands.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { ApiClient, ApiResponse } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { BulkModal } from "./dispatchModals";
import { OrderDetailPage } from "./OrderDetailPage";
import { OrderEditPage } from "./OrderEditPage";
import { OrdersPage } from "./OrdersPage";
import type { OrderEditForm, WorkKpis, WorkOrderDispatchRow } from "./workEndpoints";
import RECORDED from "./__fixtures__/work-order-candidates.recorded.json";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(() => cleanup());

type Call = { method: string; path: string; body: unknown; query?: Record<string, unknown> };
const ok = (data: unknown) => ({ status: 200, data, etag: null, notModified: false }) as ApiResponse<unknown>;
const EMPTY = { count: 0, next: null, previous: null, results: [] };

function fakeClient(calls: Call[], reads: (path: string, query: Record<string, unknown>) => unknown): ApiClient {
  const write = (method: string) => async (path: string, body?: unknown) => {
    calls.push({ method, path, body: body ?? null });
    return ok({});
  };
  return {
    get: async (path: string, options?: { query?: Record<string, unknown> }) => {
      const query = options?.query ?? {};
      calls.push({ method: "GET", path, body: null, query });
      const answer = reads(path, query);
      if (answer !== undefined) return ok(answer);
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

// ── §7.3's candidate rows ─────────────────────────────────────────────────

type Advice = {
  skill: { name: string } | null;
  has_skill: boolean;
  area_match: boolean;
  off_that_day: boolean;
  jobs_that_day: number;
  certifications_lapsed: { name: string; expired_on: string }[];
};

function advice(over: Partial<Advice> = {}): Advice {
  return {
    skill: { name: "Backflow" },
    has_skill: true,
    area_match: false,
    off_that_day: false,
    jobs_that_day: 0,
    certifications_lapsed: [],
    ...over,
  };
}

const PATEL = { kind: "person", id: "tech-patel", name: "R. Patel", best_fit: true, advice: advice({ area_match: true, jobs_that_day: 1 }) };
const ORTIZ = { kind: "person", id: "tech-ortiz", name: "D. Ortiz", best_fit: false, advice: advice({ jobs_that_day: 4 }) };
// The two the proof is about: one MISSING the skill, one whose certificate LAPSED.
const CHEN = { kind: "person", id: "tech-chen", name: "M. Chen", best_fit: false, advice: advice({ has_skill: false, off_that_day: true }) };
const LOPEZ = {
  kind: "person",
  id: "tech-lopez",
  name: "J. Lopez",
  best_fit: false,
  advice: advice({ certifications_lapsed: [{ name: "Backflow tester", expired_on: "2026-09-30" }] }),
};
const CREW_B = { kind: "crew", id: "crew-b", name: "Field crew B", best_fit: false, advice: advice() };

function page(rows: unknown[]) {
  return { count: rows.length, next: null, previous: null, results: rows };
}

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

const HELD_BY_ORTIZ = editForm({
  order_no: "WO-0043",
  dispatch_state: "scheduled",
  technician: { kind: "person", name: "D. Ortiz", slug: "d-ortiz", id: "tech-ortiz" },
  technician_id: "tech-ortiz",
});

function mountEdit(form: OrderEditForm, calls: Call[], candidates: unknown = page([PATEL, ORTIZ, CHEN, LOPEZ, CREW_B])) {
  const client = fakeClient(calls, (path, query) => {
    if (path === `/work-orders/${ORDER_ID}/edit`) return form;
    if (path === `/work-orders/${ORDER_ID}/candidates`) {
      const q = String(query.q ?? "");
      if (q === "") return candidates;
      return page([PATEL, ORTIZ, CHEN, LOPEZ, CREW_B].filter((row) => row.name.toLowerCase().includes(q.toLowerCase())));
    }
    if (path === "/work/areas") return { results: [{ id: "ar-nw", code: "NW", name: "NW" }] };
    return undefined;
  });
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

async function openPicker(): Promise<HTMLElement> {
  const box = await screen.findByRole("combobox", { name: new RegExp(t("work.edit.field.assignedTo")) });
  await waitFor(() => expect(document.querySelectorAll("[data-option-detail]").length).toBeGreaterThan(0));
  fireEvent.focus(box);
  return box;
}

function optionFor(name: string): HTMLElement {
  const row = Array.from(document.querySelectorAll<HTMLElement>("[data-option-detail]")).find((el) =>
    (el.textContent ?? "").includes(name),
  );
  if (!row) throw new Error(`${name} is not offered`);
  return row;
}

describe("P4.12 / ruling 2 — advice beside every name; nobody is refused (image 12)", () => {
  it("every candidate is offered — the one MISSING the skill and the one whose certificate LAPSED too", async () => {
    const calls: Call[] = [];
    mountEdit(editForm(), calls);
    await openPicker();
    for (const name of ["R. Patel", "D. Ortiz", "M. Chen", "J. Lopez", "Field crew B"]) {
      const row = optionFor(name);
      expect(row.getAttribute("aria-disabled")).toBeNull();
    }
  });

  it("the advice is BESIDE each name: Best fit, the skill, a missing skill, a lapsed certificate, off, jobs that day", async () => {
    const calls: Call[] = [];
    mountEdit(editForm(), calls);
    await openPicker();
    const patel = optionFor("R. Patel").textContent ?? "";
    expect(patel).toContain(t("work.assign.bestFit"));
    expect(patel).toContain(t("work.assign.advice.hasSkill", { skill: "Backflow" }));
    expect(patel).toContain(t("work.assign.advice.inArea"));
    expect(patel).toContain(t("work.assign.advice.jobs", { count: 1 }));
    const chen = optionFor("M. Chen").textContent ?? "";
    expect(chen).toContain(t("work.assign.advice.missingSkill", { skill: "Backflow" }));
    expect(chen).toContain(t("work.assign.advice.off"));
    expect(chen).not.toContain(t("work.assign.bestFit"));
    const lopez = optionFor("J. Lopez").textContent ?? "";
    expect(lopez).toContain(t("work.assign.advice.lapsed", { date: "09/30/2026" }));
    expect(optionFor("Field crew B").textContent).toContain(t("work.edit.holderKind.crew"));
  });

  it("Best fit is FIRST, whatever order the page arrived in", async () => {
    const calls: Call[] = [];
    mountEdit(editForm(), calls, page([ORTIZ, CHEN, PATEL, LOPEZ]));
    await openPicker();
    const first = document.querySelectorAll<HTMLElement>("[data-option-detail]")[0];
    expect(first.textContent).toContain("R. Patel");
  });

  it("after a pick, CLICKING the box opens the list again — the focus never left it (DEF-WRK-9608)", async () => {
    const calls: Call[] = [];
    mountEdit(editForm(), calls);
    const box = await openPicker();
    fireEvent.click(optionFor("R. Patel"));
    const panel = document.querySelector('[data-panel-state]') as HTMLElement;
    expect(panel.hidden).toBe(true);
    fireEvent.click(box);
    expect(panel.hidden).toBe(false);
  });

  it("the line under the field says it is advice only", async () => {
    const calls: Call[] = [];
    mountEdit(editForm(), calls);
    await openPicker();
    expect(screen.getByText(t("work.assign.help.adviceOnly"))).toBeDefined();
  });

  it("picking the candidate who MISSES the skill assigns them — the save is not blocked", async () => {
    const calls: Call[] = [];
    mountEdit(editForm(), calls);
    await openPicker();
    fireEvent.click(optionFor("M. Chen"));
    await userEvent.click(screen.getByRole("button", { name: /Assign ✓/ }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PATCH")).toHaveLength(1));
    const body = calls.find((c) => c.method === "PATCH")?.body as Record<string, unknown>;
    expect(body.technician_id).toBe("tech-chen");
  });

  it("the list is PAGED and SEARCHED on the server (NFR-3 / NFR-5) — never a capped list", async () => {
    const calls: Call[] = [];
    mountEdit(editForm(), calls);
    const box = await openPicker();
    const first = calls.find((c) => c.path === `/work-orders/${ORDER_ID}/candidates`);
    expect(first?.query).toMatchObject({ page: 1 });
    expect(Number(first?.query?.per)).toBeGreaterThan(0);
    await userEvent.clear(box);
    await userEvent.type(box, "Lo");
    await waitFor(() =>
      expect(calls.some((c) => c.path === `/work-orders/${ORDER_ID}/candidates` && c.query?.q === "Lo")).toBe(true),
    );
    await waitFor(() => expect(document.querySelectorAll("[data-option-detail]").length).toBe(1));
    expect(optionFor("J. Lopez")).toBeDefined();
  });

  it("the SERVER's own answer (recorded on PostgreSQL by SRV-2) draws: none disabled, a missing skill, a lapsed certificate, a crew's head-count", async () => {
    const calls: Call[] = [];
    mountEdit(editForm(), calls, RECORDED);
    await openPicker();
    const rows = Array.from(document.querySelectorAll<HTMLElement>("[data-option-detail]"));
    expect(rows).toHaveLength(RECORDED.results.length);
    expect(rows.every((row) => row.getAttribute("aria-disabled") === null)).toBe(true);
    expect(rows[0].textContent).toContain(t("work.assign.bestFit"));
    expect(optionFor("M. Chen").textContent).toContain(t("work.assign.advice.missingSkill", { skill: "Excavation" }));
    expect(optionFor("J. Okoro").textContent).toContain(t("work.assign.advice.lapsed", { date: "09/22/2026" }));
    expect(optionFor("Field crew A").textContent).toContain(t("work.assign.advice.people", { count: 2 }));
  });
});

describe("P4.4's screen half — a reassign says WHY it moves (image 13)", () => {
  it("moving the job names who had it and the new name's advice, under the field", async () => {
    const calls: Call[] = [];
    mountEdit(HELD_BY_ORTIZ, calls);
    await openPicker();
    fireEvent.click(optionFor("R. Patel"));
    const help = document.querySelector('[data-field-help="assigned-to"]')?.textContent ?? "";
    expect(help).toContain(t("work.assign.help.wasPrefix", { name: "D. Ortiz" }));
    expect(help).toContain("R. Patel");
    expect(help).toContain(t("work.assign.advice.jobs", { count: 1 }));
  });

  it("Why it moves appears only once the holder moves, and is REQUIRED", async () => {
    const calls: Call[] = [];
    mountEdit(HELD_BY_ORTIZ, calls);
    await openPicker();
    expect(screen.queryByLabelText(new RegExp(t("work.assign.why.label")))).toBeNull();
    fireEvent.click(optionFor("R. Patel"));
    const why = await screen.findByLabelText(new RegExp(t("work.assign.why.label")));
    expect(why).toBeDefined();
    await userEvent.click(screen.getByRole("button", { name: /Reassign ✓/ }));
    expect(await screen.findByText(t("work.assign.why.required"))).toBeDefined();
    expect(calls.filter((c) => c.method === "PATCH")).toHaveLength(0);
  });

  it("the reason travels with the save, in the dispatcher's words", async () => {
    const calls: Call[] = [];
    mountEdit(HELD_BY_ORTIZ, calls);
    await openPicker();
    fireEvent.click(optionFor("R. Patel"));
    await userEvent.selectOptions(
      await screen.findByLabelText(new RegExp(t("work.assign.why.label"))),
      "workload",
    );
    await userEvent.type(screen.getByLabelText(t("work.assign.why.note")), "D. Ortiz has four jobs that day.");
    await userEvent.click(screen.getByRole("button", { name: /Reassign ✓/ }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PATCH")).toHaveLength(1));
    const body = calls.find((c) => c.method === "PATCH")?.body as Record<string, unknown>;
    expect(body.technician_id).toBe("tech-patel");
    expect(body.reason).toBe(`${t("work.assign.why.reasons.workload")} — D. Ortiz has four jobs that day.`);
  });

  it("taking the job off its holder to *Nobody yet* asks why too — the server refuses a move off somebody without one", async () => {
    const calls: Call[] = [];
    mountEdit(HELD_BY_ORTIZ, calls);
    await openPicker();
    const nobody = Array.from(document.querySelectorAll<HTMLElement>('[role="option"]')).find(
      (el) => el.textContent === t("work.edit.option.unassigned"),
    ) as HTMLElement;
    fireEvent.click(nobody);
    expect(await screen.findByLabelText(new RegExp(t("work.assign.why.label")))).toBeDefined();
    await userEvent.selectOptions(screen.getByLabelText(new RegExp(t("work.assign.why.label"))), "offSick");
    await userEvent.click(screen.getByRole("button", { name: /Reassign ✓/ }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PATCH")).toHaveLength(1));
    const body = calls.find((c) => c.method === "PATCH")?.body as Record<string, unknown>;
    expect(body.technician_id).toBeNull();
    expect(body.reason).toBe(t("work.assign.why.reasons.offSick"));
  });

  it("the effects box promises the reason in the audit", async () => {
    const calls: Call[] = [];
    mountEdit(HELD_BY_ORTIZ, calls);
    await openPicker();
    fireEvent.click(optionFor("R. Patel"));
    const box = document.querySelector('[data-consequence="change-effects"]') as HTMLElement;
    expect(box.textContent).toContain(t("work.edit.effects.auditBoth"));
    expect(t("work.edit.effects.auditBoth")).toContain("reason");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// P4.13 — bulk assign (image 02)
// ══════════════════════════════════════════════════════════════════════════

describe("P4.13 — Assign N orders asks who and when, says how many, and ADVISES", () => {
  function mountBulk(calls: Call[], submitted: unknown[], held = 0) {
    const client = fakeClient(calls, (path) => {
      // WO-0040 needs Backflow, which M. Chen lacks; WO-0043 needs nothing.
      if (path === "/work-orders/wo-0040/candidates") return page([PATEL, ORTIZ, CHEN, LOPEZ]);
      if (path === "/work-orders/wo-0043/candidates")
        return page([PATEL, ORTIZ, { ...CHEN, advice: advice({ skill: null, off_that_day: true }) }, LOPEZ].map((row) => ({ ...row, advice: { ...row.advice, skill: null, has_skill: true } })));
      return undefined;
    });
    const queryClient = freshClient();
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/${TENANT}/work/orders`]}>
          <Routes>
            <Route
              path="/:tenant/work/orders"
              element={
                <BulkModal
                  act="assign"
                  ids={["wo-0040", "wo-0043"]}
                  held={held}
                  priorities={[]}
                  client={client}
                  onSubmit={async (body) => {
                    submitted.push(body);
                    return { ok: true } as never;
                  }}
                  onClose={() => undefined}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it("the title says how many", async () => {
    mountBulk([], []);
    expect(await screen.findByText(t("work.orders.bulk.title.assignCount", { count: 2 }))).toBeDefined();
  });

  it("the candidate missing a skill on ONE order is still offered — no intersection removes them", async () => {
    mountBulk([], []);
    await screen.findByRole("combobox", { name: new RegExp(t("work.orders.bulk.holder")) });
    await waitFor(() => expect(document.querySelectorAll("[data-option-detail]").length).toBe(4));
    const chen = optionFor("M. Chen");
    expect(chen.getAttribute("aria-disabled")).toBeNull();
    expect(chen.textContent).toContain(t("work.assign.advice.missingSkill", { skill: "Backflow" }));
  });

  it("an advice line under Who is going names who lacks a skill and who is off", async () => {
    mountBulk([], []);
    await waitFor(() => expect(document.querySelectorAll("[data-option-detail]").length).toBe(4));
    const line = document.querySelector('[data-field-help="holder"]')?.textContent ?? "";
    expect(line).toContain(t("work.assign.bulk.missing", { count: 1 }));
    expect(line).toContain(t("work.assign.bulk.off", { names: "M. Chen" }));
  });

  it("orders somebody already holds: the dialog asks WHY they move and sends the reason (SRV-2 refuses each one without)", async () => {
    const submitted: unknown[] = [];
    mountBulk([], submitted, 1);
    const box = await screen.findByRole("combobox", { name: new RegExp(t("work.orders.bulk.holder")) });
    await waitFor(() => expect(document.querySelectorAll("[data-option-detail]").length).toBe(4));
    expect(screen.getByText(t("work.assign.bulk.held", { count: 1 }))).toBeDefined();
    fireEvent.focus(box);
    fireEvent.click(optionFor("R. Patel"));
    await userEvent.click(screen.getByRole("button", { name: t("work.orders.bulk.submit.assign") }));
    expect(await screen.findByText(t("work.assign.why.required"))).toBeDefined();
    expect(submitted).toHaveLength(0);
    await userEvent.selectOptions(screen.getByLabelText(new RegExp(t("work.assign.why.label"))), "closer");
    await userEvent.click(screen.getByRole("button", { name: t("work.orders.bulk.submit.assign") }));
    await waitFor(() => expect(submitted).toHaveLength(1));
    expect(submitted[0]).toMatchObject({ technician_id: "tech-patel", reason: t("work.assign.why.reasons.closer") });
  });

  it("choosing the one who lacks a skill still assigns — the dialog posts technician_id", async () => {
    const submitted: unknown[] = [];
    mountBulk([], submitted);
    const box = await screen.findByRole("combobox", { name: new RegExp(t("work.orders.bulk.holder")) });
    await waitFor(() => expect(document.querySelectorAll("[data-option-detail]").length).toBe(4));
    fireEvent.focus(box);
    fireEvent.click(optionFor("M. Chen"));
    await userEvent.click(screen.getByRole("button", { name: t("work.orders.bulk.submit.assign") }));
    await waitFor(() => expect(submitted).toHaveLength(1));
    expect(submitted[0]).toMatchObject({ technician_id: "tech-chen" });
  });
});

// ══════════════════════════════════════════════════════════════════════════
// P4.1 — technician acceptance on 1·1 and 1·2; P1.27 — Assign… on the order
// ══════════════════════════════════════════════════════════════════════════

const KPIS: WorkKpis = {
  open_total: 3,
  unassigned: { count: 0 },
  due_today: { count: 0, urgent: 0 },
  in_field: { count: 0 },
  awaiting_approval: { count: 0 },
  overdue: { count: 0, worst: null },
};

function listRow(id: string, name: string, acceptance: unknown): WorkOrderDispatchRow {
  return {
    id,
    order_no: id.toUpperCase(),
    type: "Meter set",
    premise: { id: "p-1", premise_no: "P-00101", address: "14 Willow Bend" },
    service: "water",
    state: "planned",
    outcome: null,
    mode: "our_crew",
    is_gate: false,
    connection: null,
    account: null,
    raised_at: "2026-09-24T12:00:00Z",
    priority: null,
    technician: { kind: "person", name, slug: name },
    due_at: null,
    window_start: null,
    window_end: null,
    dispatch_state: "scheduled",
    source: null,
    source_ref: null,
    area: null,
    technician_acceptance: acceptance,
  } as unknown as WorkOrderDispatchRow;
}

describe("P4.1 — a dispatcher sees who accepted", () => {
  it("the Orders list says Accepted, Declined or not yet, under the technician", async () => {
    const calls: Call[] = [];
    const rows = [
      listRow("wo-1", "R. Patel", { state: "accepted", at: "2026-09-24T12:00:00Z", reason: null }),
      listRow("wo-2", "D. Ortiz", { state: "declined", at: "2026-09-24T12:00:00Z", reason: "Van broke down" }),
      listRow("wo-3", "M. Chen", { state: "pending", at: null, reason: null }),
    ];
    const client = fakeClient(calls, (path) => {
      if (path === "/work-orders") return { count: 3, next: null, previous: null, results: rows, open_total: 3 };
      if (path === "/work/kpis") return KPIS;
      if (path === "/work/areas") return { results: [] };
      if (path === "/work/crews") return { ...EMPTY, counts: { rows: 0, people: 0, crews: 0, contractors: 0 } };
      return undefined;
    });
    render(
      <QueryClientProvider client={freshClient()}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}/work/orders`]}>
            <Routes>
              <Route path="/:tenant/work/orders" element={<OrdersPage client={client} />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    await screen.findByText("R. Patel");
    const cellOf = (name: string) => screen.getByText(name).closest("td") as HTMLElement;
    expect(within(cellOf("R. Patel")).getByText(t("work.orders.acceptance.accepted"))).toBeDefined();
    expect(within(cellOf("D. Ortiz")).getByText(t("work.orders.acceptance.declined"))).toBeDefined();
    expect(within(cellOf("M. Chen")).getByText(t("work.orders.acceptance.pending"))).toBeDefined();
  });
});

const DETAIL_ID = "0190a0b1-0000-7000-8000-000000000043";

function detail(over: Record<string, unknown>) {
  return {
    id: DETAIL_ID,
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
    raised_at: "2026-09-24T06:02:00Z",
    priority: null,
    technician: { kind: "person", name: "D. Ortiz", slug: "d-ortiz" },
    due_at: null,
    window_start: null,
    window_end: null,
    dispatch_state: "scheduled",
    source: "dispatcher",
    source_ref: null,
    area: null,
    custom_data: {},
    shape: "open",
    hold: null,
    accepted: null,
    technician_acceptance: { state: "accepted", at: "2026-09-24T07:00:00Z", reason: null },
    ...over,
  };
}

function mountDetail(order: Record<string, unknown>) {
  const calls: Call[] = [];
  const client = fakeClient(calls, (path) => {
    if (path === `/work-orders/${DETAIL_ID}`) return order;
    if (path.startsWith(`/work-orders/${DETAIL_ID}/`)) return [];
    if (path === "/work/hold-reasons") return [];
    return [];
  });
  return render(
    <QueryClientProvider client={freshClient()}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/work/orders/${DETAIL_ID}`]}>
          <Routes>
            <Route path="/:tenant/work/orders/:orderNo" element={<OrderDetailPage client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("P4.1 and P1.27 on the order (1·2)", () => {
  it("the line under the title says the technician accepted", async () => {
    const { container } = mountDetail(detail({}));
    await waitFor(() => expect(container.querySelector("[data-metaline]")).not.toBeNull());
    const line = container.querySelector("[data-metaline]")?.textContent ?? "";
    expect(line).toContain(`D. Ortiz · ${t("work.orders.acceptance.accepted")}`);
  });

  it("a job nobody holds reads Assign…, not Reassign…", async () => {
    mountDetail(detail({ technician: null, technician_acceptance: null, dispatch_state: "queued" }));
    expect(await screen.findByRole("button", { name: t("work.order.actions.assign") })).toBeDefined();
    expect(screen.queryByRole("button", { name: t("work.order.actions.reassign") })).toBeNull();
  });

  it("a held job still reads Reassign…", async () => {
    mountDetail(detail({}));
    expect(await screen.findByRole("button", { name: t("work.order.actions.reassign") })).toBeDefined();
  });
});
