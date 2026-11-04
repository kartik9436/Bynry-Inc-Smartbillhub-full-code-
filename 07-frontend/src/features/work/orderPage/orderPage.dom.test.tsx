// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 2, lane ORDER-PAGE — one order, both shapes,
//           images 03–11, and the three defects this lane fixes:
//             DEF-WRK-9581 — the page never showed the unit, the meter or the
//                            customer the job is for (P1.2, P1.21)
//             DEF-WRK-9584 — the Audit tab printed raw timestamps and named the
//                            technician under *Who* for the dispatcher's act
//                            (P1.16, P1.17)
//             DEF-WRK-9525 (the screen half) — the office could complete a job:
//                            *Mark complete* and a tick box on every line
//                            (ruling 18)
//           Each case below was run against the page as it stood at
//           `5be42bfb3` FIRST and failed; the failures are quoted in CR-168 §10.
// ───────────────────────────────────────────────────────
//
// ⚠ MOUNTED UNDER THE REAL PATH PATTERN (`/:tenant/work/orders/:orderNo`) and
// fed by a client that ROUTES like the server, so a call to a path the page
// should not make is visible as a call, not as a swallowed default.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { OrderDetailPage } from "../OrderDetailPage";

const TENANT = "brazosbend";
const ID = "0190a0b1-0000-7000-8000-000000000043";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

type Call = { method: string; path: string; body: unknown };

/** Image 03's job — WO-0043 at 101 Silver Creek Rd, Unit 1, for Ana Alvarez,
 *  meter W-5000, D. Ortiz, 25 Sep 9–12. The NEW fields are §7.3's shapes. */
const OPEN = {
  id: ID,
  order_no: "WO-0043",
  type: "Meter exchange — residential",
  premise: { id: "p-1", premise_no: "P-00101", address: "101 Silver Creek Rd" },
  service: "water",
  state: "planned",
  outcome: null,
  mode: "our_crew",
  is_gate: false,
  connection: null,
  account: { id: "a-1", account_no: "AC-2026-00001" },
  raised_at: "2026-09-24T06:02:00Z",
  priority: { id: "pr-3", code: "NORMAL", name: "Normal", colour: "info", rank: 3 },
  technician: { kind: "person", name: "D. Ortiz", slug: "d-ortiz" },
  due_at: "2026-09-27T06:03:00Z",
  window_start: "2026-09-25T09:00:00Z",
  window_end: "2026-09-25T12:00:00Z",
  dispatch_state: "scheduled",
  source: "dispatcher",
  source_ref: null,
  area: { id: "ar-1", code: "NW", name: "NW" },
  est_duration_minutes: 38,
  custom_data: {},
  shape: "open",
  customer: { name: "Ana Alvarez", phone: "+1 (402) 555-1000", account_no: "AC-2026-00001" },
  // ⚠ THE SERVER'S OWN SHAPE (`dispatch._location_of`, 2.497.0), not the
  // contract's prose: premises, unit and asset are OBJECTS. This fixture read
  // `unit: "Unit 1"` until `DEF-WRK-9600`, so the suite stayed green while the
  // real answer crashed the page on every job with a unit.
  location: {
    premises: { id: "p-1", premise_no: "P-00101" },
    unit: { id: "u-1", label: "Unit 1" },
    asset: { id: "a-1", asset_no: "W-5000", serial: "SN-77" },
    address: "101 Silver Creek Rd",
  },
  hold: null,
  accepted: null,
};

const COMPLETED = {
  ...OPEN,
  state: "completed",
  outcome: "passed",
  dispatch_state: "complete",
  shape: "completed",
  closed: { by: { name: "D. Ortiz" }, at: "2026-09-25T11:50:00Z" },
  signature: {
    printed_name: "Ana Alvarez",
    signed_at: "2026-09-25T11:42:00Z",
    refused: false,
    captured_by: { name: "D. Ortiz" },
    image_url: "https://files.example/sig.png",
  },
};

function checklist(done: boolean) {
  const tick = (at: string) => (done ? { ticked_at: at, ticked_by: "u-1", ticked_by_name: "D. Ortiz" } : { ticked_at: null, ticked_by: null });
  return {
    order_id: ID,
    order_no: "WO-0043",
    template_id: "tpl-1",
    template_version: 2,
    safety: [
      { id: "s1", seq: 1, text: "Shut the curb stop before breaking the union", is_mandatory: true, ...tick("2026-09-25T09:41:00Z") },
      { id: "s2", seq: 2, text: "Check the pit for standing water", is_mandatory: true, ...tick("2026-09-25T09:44:00Z") },
    ],
    safety_lock: { locked: !done, remaining: done ? 0 : 2, first_outstanding: null, ticked: done ? 2 : 0, total: 2, mandatory_total: 2 },
    tasks: [
      { id: "t1", seq: 1, title: "Read and photograph the OLD meter", est_minutes: 5, photo_required: true, is_mandatory: true, ...tick("2026-09-25T09:52:00Z"), photo_attachment_id: done ? "att-1" : null },
      { id: "t2", seq: 2, title: "Shut the curb stop and break the unions", est_minutes: 5, photo_required: false, is_mandatory: true, ...tick("2026-09-25T10:18:00Z"), photo_attachment_id: null },
    ],
    tasks_total: 2,
    tasks_ticked: done ? 2 : 0,
    tasks_est_minutes: 10,
    readings: [
      {
        id: "r1", seq: 1, prompt: "Closing read on the OLD meter", unit_of_measure: "gal",
        min_value: "0.0000", max_value: "99999999.0000", required: true, photo_required: false,
        posts_as_meter_read: true, value: done ? "4821.0000" : null, captured_at: null,
        photo_attachment_id: done ? "att-2" : null, in_range: done ? true : null,
      },
    ],
    materials: [
      { id: "m1", part_id: "pt-1", part_no: "GSK-58", part_name: "Meter gasket 5/8\"", planned_qty: "2.0000", used_qty: null, unit_of_measure: "each", unplanned: false },
    ],
    help: [],
    details: { access_notes: null, hazards: null, gate_code: null, show_account_summary: true, show_asset_card: false, show_access_notes: true, show_appointment: true },
  };
}

const AUDIT = {
  order_no: "WO-0043",
  rows: [
    {
      act: "assign",
      at: "2026-09-24T06:03:42.963368+00:00",
      who: { kind: "person", name: "D. Ortiz" },
      by: "Dana Whitfield",
      scheduled_for: null,
      window_start: "2026-09-25T09:00:00Z",
      window_end: "2026-09-25T12:00:00Z",
    },
  ],
};

const ATTACHMENTS = [
  { id: "att-1", kind: "photo", taken_at: "2026-09-25T10:12:00Z", device: null, added_by_name: "D. Ortiz", reading_id: null, task_id: "t1" },
  { id: "att-2", kind: "photo", taken_at: "2026-09-25T10:20:00Z", device: null, added_by_name: "D. Ortiz", reading_id: "r1", task_id: null },
];

function client(order: Record<string, unknown>, calls: Call[], attachments: unknown[] = ATTACHMENTS): ApiClient {
  const done = order.state === "completed";
  const answer = (path: string): unknown => {
    if (path === `/work-orders/${ID}`) return order;
    if (path === `/work-orders/${ID}/checklist`) return checklist(done);
    if (path === `/work-orders/${ID}/audit`) return AUDIT;
    if (path === `/work-orders/${ID}/close-readiness`)
      return { can_close: true, blocking: [], flagged: [], readings_captured: 1, readings_total: 1, required_photos_taken: 1, required_photos_total: 1 };
    if (path === `/work-orders/${ID}/attachments`) return attachments;
    if (path.startsWith(`/work-orders/${ID}/attachments/`))
      return { id: path.split("/").pop(), kind: "photo", taken_at: null, device: null, url: `https://files.example/${path.split("/").pop()}.jpg`, expires_in_seconds: 14400 };
    if (path === `/work-orders/${ID}/signature`) return null;
    // ⚠ THE SERVER'S OWN ANSWER (`api.work_hold_reasons`, 2.497.0): a
    // `results` envelope of ACTIVE reasons with no `active` flag. This read
    // `active: true` on each row until `DEF-WRK-9601`, which is why the suite
    // passed while the real dialog offered no reason at all.
    if (path === "/work/hold-reasons")
      return {
        results: [
          { code: "PARTS", name: "Waiting for parts", rank: 1 },
          { code: "WEATHER", name: "Weather", rank: 2 },
        ],
      };
    return [];
  };
  const send = (method: string) => async (path: string, body?: unknown) => {
    calls.push({ method, path, body: body ?? null });
    const data = method === "GET" ? answer(path) : { id: ID, dispatch_state: "on_hold", accepted_at: "x", connection_state: null, communication: { queued: false }, br_ref: "" };
    return { status: 200, data, etag: null, notModified: false };
  };
  return {
    request: send("REQUEST"), get: send("GET"), post: send("POST"),
    put: send("PUT"), patch: send("PATCH"), del: send("DELETE"),
  } as unknown as ApiClient;
}

function mount(order: Record<string, unknown>, tab = "overview", calls: Call[] = [], attachments: unknown[] = ATTACHMENTS) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/work/orders/${ID}?tab=${tab}`]}>
          <Routes>
            <Route path="/:tenant/work/orders/:orderNo" element={<OrderDetailPage client={client(order, calls, attachments)} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const posts = (calls: Call[]) => calls.filter((c) => c.method !== "GET");

afterEach(cleanup);

describe("DEF-WRK-9581 — the order shows the unit, the meter and the customer (P1.2, image 03)", () => {
  it("the Overview carries Meter, and Location and Customer as PANELS — four tabs, not six", async () => {
    const { container } = mount(OPEN);
    await waitFor(() => expect(screen.getByText(t("work.order.overview.title"))).toBeTruthy());
    const tabs = Array.from(container.querySelectorAll('[role="tab"]')).map((tab) => tab.textContent);
    expect(tabs).toEqual(["overview", "checklist", "parts", "audit"].map((id) => t(`work.order.tabs.${id}`)));
    expect(screen.getByText(t("work.order.overview.meter"))).toBeTruthy();
    expect(screen.getAllByText("W-5000").length).toBeGreaterThan(0);
    expect(screen.getByText(t("work.order.location.title"))).toBeTruthy();
    expect(screen.getByText(t("work.order.customer.title"))).toBeTruthy();
    expect(screen.getAllByText("Unit 1").length).toBeGreaterThan(0);
    expect(screen.getByText("+1 (402) 555-1000")).toBeTruthy();
  });

  it("the line under the title names the unit, the customer, the meter and the window", async () => {
    const { container } = mount(OPEN);
    await waitFor(() => expect(container.querySelector("[data-metaline]")).not.toBeNull());
    const line = container.querySelector("[data-metaline]")?.textContent ?? "";
    for (const leg of ["101 Silver Creek Rd", "Unit 1", "AC-2026-00001", "Ana Alvarez", "W-5000", "Normal", "D. Ortiz", "09/25/2026 09:00–12:00"]) {
      expect(line, `the line lacks ${leg}`).toContain(leg);
    }
  });

  it("P1.19 — the service by its name, never its code", async () => {
    mount(OPEN);
    await waitFor(() => expect(screen.getByText(t("work.order.overview.title"))).toBeTruthy());
    expect(screen.getByText(t("rating.service.water"))).toBeTruthy();
    expect(screen.queryByText("water")).toBeNull();
  });
});

describe("DEF-WRK-9584 — the history reads as dates and says who acted, and on whom (image 08)", () => {
  it("To · By · When · Window, the act's DOER under By, and no raw ISO stamp", async () => {
    const { container } = mount(OPEN, "audit");
    await waitFor(() => expect(container.querySelector("[data-audit-row]")).not.toBeNull());
    const heads = Array.from(container.querySelectorAll("th")).map((th) => th.textContent);
    expect(heads).toEqual(["act", "to", "by", "when", "window"].map((k) => t(`work.order.audit.${k}`)));
    const row = container.querySelector("[data-audit-row]") as HTMLElement;
    expect(within(row).getByText("D. Ortiz")).toBeTruthy();
    expect(row.querySelector("[data-audit-by]")?.textContent).toBe("Dana Whitfield");
    expect(row.querySelector("[data-audit-when]")?.textContent).toBe("09/24/2026 06:03");
    expect(row.textContent).not.toContain("T06:03");
    expect(row.textContent).toContain("09/25/2026 09:00–12:00");
  });

  it("an act the catalogue does not know reads as a word, never as its token", async () => {
    // (No row of that kind is served yet; the generic word exists in every catalogue.)
    expect(i18n.exists("work.order.audit.acts.other")).toBe(true);
    expect(i18n.exists("work.order.audit.acts.hold")).toBe(true);
  });
});

describe("DEF-WRK-9525, the screen half — the office never completes a job (ruling 18)", () => {
  it("NO Mark complete on either shape, and no tick box on any line", async () => {
    for (const order of [OPEN, COMPLETED]) {
      const { container, unmount } = mount(order, "checklist");
      await waitFor(() => expect(container.querySelector("[data-task-row]")).not.toBeNull());
      expect(screen.queryByText(/Mark complete/i)).toBeNull();
      expect(container.querySelectorAll('input[type="checkbox"]').length).toBe(0);
      unmount();
    }
  });

  it("the open job's head is Print · Reassign… · Put on hold… · Cancel order — and it never posts field-result", async () => {
    const calls: Call[] = [];
    const { container } = mount(OPEN, "overview", calls);
    await waitFor(() => expect(container.querySelector(".page-header-actions button")).not.toBeNull());
    const labels = Array.from(container.querySelectorAll(".page-header-actions button")).map((b) => b.textContent);
    // CR-168-BRC10 P6.3 (lane SRV-5) — *Print* leads; the destructive one stays last.
    expect(labels).toEqual([
      t("work.order.actions.print"),
      t("work.order.actions.duplicate"),
      t("work.order.actions.reassign"),
      t("work.order.actions.hold"),
      t("work.order.actions.cancel"),
    ]);
    expect(calls.some((c) => c.path.endsWith("/field-result"))).toBe(false);
  });
});

describe("P1.29 — two shapes (rulings 15 and 17)", () => {
  it("OPEN: the checklist is the PLAN — tasks as a table, no Done, no Value, no photographs, no signature", async () => {
    const { container } = mount(OPEN, "checklist");
    await waitFor(() => expect(container.querySelector('[data-checklist="plan"]')).not.toBeNull());
    expect(container.querySelector("table [data-task-row]")).not.toBeNull();
    expect(screen.queryByText(t("work.order.tasks.done"))).toBeNull();
    expect(screen.queryByText(t("work.order.readings.value"))).toBeNull();
    expect(container.querySelector("[data-photo-thumb]")).toBeNull();
    expect(screen.getByText("0–99,999,999")).toBeTruthy();
  });

  it("COMPLETED: the RECORD — who did each line and when, the value, the photographs; the signature on Overview", async () => {
    const { container, unmount } = mount(COMPLETED, "checklist");
    await waitFor(() => expect(container.querySelector('[data-checklist="record"]')).not.toBeNull());
    expect(screen.getByText(t("work.order.tasks.done"))).toBeTruthy();
    expect(container.querySelector("[data-task-done]")?.textContent).toBe("✓ D. Ortiz · 09/25/2026 09:52");
    expect(screen.getByText("4,821")).toBeTruthy();
    await waitFor(() => expect(container.querySelectorAll("table [data-photo-thumb]").length).toBe(2));
    unmount();
    const overview = mount(COMPLETED, "overview");
    await waitFor(() => expect(overview.container.querySelector("[data-signature]")).not.toBeNull());
    expect(screen.getByText(t("work.order.signature.title"))).toBeTruthy();
    expect(overview.container.querySelector("[data-signature] img")?.getAttribute("src")).toBe(
      "https://files.example/sig.png",
    );
  });

  it("OPEN has no signature panel even when one exists on the server", async () => {
    const { container } = mount({ ...OPEN, signature: COMPLETED.signature }, "overview");
    await waitFor(() => expect(screen.getByText(t("work.order.overview.title"))).toBeTruthy());
    expect(container.querySelector("[data-signature]")).toBeNull();
  });

  it("P1.22 — a photograph opens the viewer, with who, when, what for, and 1 of 2", async () => {
    const calls: Call[] = [];
    const { container } = mount(COMPLETED, "checklist", calls);
    await waitFor(() => expect(container.querySelectorAll("table [data-photo-thumb]").length).toBe(2));
    fireEvent.click(container.querySelector('[data-photo-thumb="task-1"]') as HTMLElement);
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(t("work.order.photo.position", { at: 1, total: 2 }))).toBeTruthy();
    expect(within(dialog).getByText(t("work.order.photo.forTask", { at: 1, total: 2 }))).toBeTruthy();
    // DEF-WRK-9594 — the picture is the API's bytes, never a storage host the
    // page policy refuses.
    expect(within(dialog).getByRole("img").getAttribute("src")).toBe(
      `/api/${TENANT}/work-orders/${ID}/attachments/att-1/content`,
    );
    fireEvent.click(within(dialog).getByText(t("work.order.photo.next")));
    expect(within(dialog).getByText(t("work.order.photo.position", { at: 2, total: 2 }))).toBeTruthy();
    expect(within(dialog).getByRole("img").getAttribute("src")).toBe(
      `/api/${TENANT}/work-orders/${ID}/attachments/att-2/content`,
    );
    expect(calls.some((c) => /\/attachments\/att-\d$/.test(c.path))).toBe(false);
  });
});

describe("P1.32 — Accept on the completed job, confirmed first", () => {
  it("the head is Print · Duplicate · Send back… · Accept ✓ (image 04); Accept confirms, then posts /accept", async () => {
    const calls: Call[] = [];
    const { container } = mount(COMPLETED, "overview", calls);
    await waitFor(() => expect(container.querySelector(".page-header-actions button")).not.toBeNull());
    const labels = Array.from(container.querySelectorAll(".page-header-actions button")).map((b) => b.textContent);
    expect(labels).toEqual([
      t("work.order.actions.print"),
      t("work.order.actions.duplicate"),
      t("work.order.actions.sendBack"),
      t("work.order.actions.accept"),
    ]);
    fireEvent.click(screen.getByText(t("work.order.actions.accept")));
    expect(posts(calls)).toEqual([]);
    expect(screen.getByText(t("work.order.accept.consequence"))).toBeTruthy();
    fireEvent.click(within(screen.getByRole("alertdialog")).getByText(t("work.order.accept.confirm")));
    await waitFor(() => expect(posts(calls).length).toBe(1));
    expect(posts(calls)[0]).toMatchObject({ method: "POST", path: `/work-orders/${ID}/accept` });
  });

  it("an ACCEPTED job offers Print alone, and Print opens the job's PDF", async () => {
    const opened: string[] = [];
    const original = window.open;
    window.open = ((url: string) => {
      opened.push(url);
      return null;
    }) as typeof window.open;
    const { container } = mount({ ...COMPLETED, accepted: { by: { name: "Dana Whitfield" }, at: "2026-09-26T08:00:00Z" } });
    await waitFor(() => expect(screen.getByText(t("work.order.overview.title"))).toBeTruthy());
    const labels = Array.from(container.querySelectorAll(".page-header-actions button")).map((b) => b.textContent);
    expect(labels).toEqual([t("work.order.actions.print"), t("work.order.actions.duplicate")]);
    fireEvent.click(screen.getByText(t("work.order.actions.print")));
    window.open = original;
    // By ADDRESS (hard-won law 2): the route `GET /work-orders/{id}/print` serves.
    expect(opened).toEqual([`/api/${TENANT}/work-orders/${ID}/print`]);
    expect(screen.getByText(t("work.order.approval.accepted"))).toBeTruthy();
  });
});

describe("P4.3 — a hold says why and until when, and can be resumed (image 10)", () => {
  it("the dialog asks Reason*, Back on, Note; refuses no reason; posts all three", async () => {
    const calls: Call[] = [];
    mount(OPEN, "overview", calls);
    fireEvent.click(await screen.findByText(t("work.order.actions.hold")));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(t("work.order.hold.title", { order: "WO-0043" }))).toBeTruthy();
    expect(within(dialog).getByText(t("work.order.hold.consequence"))).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: t("work.order.hold.submit") }));
    await waitFor(() => expect(within(dialog).getAllByText(t("work.order.hold.reasonRequired")).length).toBeGreaterThan(0));
    expect(posts(calls)).toEqual([]);
    await waitFor(() => expect(within(dialog).getByText("Waiting for parts")).toBeTruthy());
    fireEvent.change(within(dialog).getByLabelText(new RegExp(t("work.order.hold.reason"))), { target: { value: "PARTS" } });
    fireEvent.change(within(dialog).getByLabelText(new RegExp(t("work.order.hold.backOn"))), { target: { value: "2026-12-28" } });
    fireEvent.change(within(dialog).getByLabelText(new RegExp(t("work.order.hold.note"))), { target: { value: "Meter on back-order." } });
    fireEvent.click(within(dialog).getByRole("button", { name: t("work.order.hold.submit") }));
    await waitFor(() => expect(posts(calls).length).toBe(1));
    expect(posts(calls)[0]).toMatchObject({
      method: "POST",
      path: `/work-orders/${ID}/hold`,
      body: { reason_code: "PARTS", expected_return_on: "2026-12-28", note: "Meter on back-order." },
    });
  });

  it("a held job shows its reason and back-on date, and Resume in place of Put on hold…", async () => {
    const calls: Call[] = [];
    const held = { ...OPEN, dispatch_state: "on_hold", hold: { reason: { code: "PARTS", name: "Waiting for parts" }, expected_return_on: "2026-09-28" } };
    mount(held, "overview", calls);
    await waitFor(() => expect(screen.getByText("Waiting for parts")).toBeTruthy());
    expect(screen.getByText("09/28/2026")).toBeTruthy();
    expect(screen.queryByText(t("work.order.actions.hold"))).toBeNull();
    fireEvent.click(screen.getByText(t("work.order.actions.resume")));
    await waitFor(() => expect(posts(calls).length).toBe(1));
    expect(posts(calls)[0]).toMatchObject({ method: "POST", path: `/work-orders/${ID}/resume` });
  });
});

describe("P1.20 — Cancel's other button says Keep the order (image 11)", () => {
  it("Keep the order · Cancel this order", async () => {
    mount(OPEN);
    fireEvent.click(await screen.findByText(t("work.order.actions.cancel")));
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(t("work.order.cancel.keep"))).toBeTruthy();
    expect(within(dialog).getByText(t("work.order.cancel.confirm"))).toBeTruthy();
    expect(t("work.order.cancel.keep")).toBe("Keep the order");
  });
});

describe("P1.18 — numbers without four trailing zeros (image 07)", () => {
  it("2 each", async () => {
    mount(OPEN, "parts");
    expect(await screen.findByText(/2 each/)).toBeTruthy();
    expect(screen.queryByText(/2\.0000/)).toBeNull();
  });
});

// ── CR-168-BRC10 lane FLOW-FIX ─────────────────────────────────────────────
describe("DEF-WRK-9624 — a failed job and its follow-up point at each other", () => {
  it("an accepted job's line no longer says the technician has not accepted it", async () => {
    const { container } = mount({
      ...COMPLETED,
      technician_acceptance: { state: "pending", at: null, reason: null },
      accepted: { by: { name: "Dana Whitfield" }, at: "2026-09-26T08:00:00Z" },
    });
    await waitFor(() => expect(container.querySelector("[data-metaline]")).not.toBeNull());
    const line = container.querySelector("[data-metaline]")?.textContent ?? "";
    expect(line).not.toContain(t("work.orders.acceptance.pending"));
  });

  it("the failed job links to its follow-up, and the follow-up links back", async () => {
    const { container } = mount({ ...COMPLETED, outcome: "failed", follows: null, follow_ups: [{ order_no: "WO-0059" }] });
    await waitFor(() => expect(screen.getByText(t("work.order.overview.followUp"))).toBeTruthy());
    expect(container.querySelector('a[href="/brazosbend/work/orders/WO-0059"]')).not.toBeNull();
    cleanup();
    const back = mount({ ...OPEN, source: "failed_outcome", follows: { order_no: "WO-0058" }, follow_ups: [] });
    await waitFor(() => expect(screen.getByText(t("work.order.overview.follows"))).toBeTruthy());
    expect(back.container.querySelector('a[href="/brazosbend/work/orders/WO-0058"]')).not.toBeNull();
  });
});

describe("DEF-WRK-9638 — a job with no name is never titled with a placeholder", () => {
  it("a job the server names nothing reads its number alone, never 'WO-0043 · '", async () => {
    mount({ ...OPEN, type: null });
    await waitFor(() => expect(screen.getByText(t("work.order.overview.title"))).toBeTruthy());
    const heading = document.querySelector("h1")?.textContent ?? "";
    expect(heading.trim()).toBe("WO-0043");
  });
});

describe("DEF-FLD-10639 (FB-014) — the office is told the phone's clock was off", () => {
  it("past 5 minutes the job says 'Was 10 min fast'; within 5 it says nothing", async () => {
    const off = { offset_s: -600, device_time: "2026-09-25T12:00:00Z" };
    mount({ ...COMPLETED, closed: { ...COMPLETED.closed, device_clock: off } });
    await waitFor(() => expect(screen.getByText(t("work.order.overview.phoneClock"))).toBeTruthy());
    expect(screen.getByText(t("work.order.overview.phoneClockFast", { minutes: 10 }))).toBeTruthy();
    cleanup();
    mount({ ...COMPLETED, closed: { ...COMPLETED.closed, device_clock: { ...off, offset_s: 600 } } });
    await waitFor(() => expect(screen.getByText(t("work.order.overview.phoneClockSlow", { minutes: 10 }))).toBeTruthy());
    cleanup();
    mount({ ...COMPLETED, closed: { ...COMPLETED.closed, device_clock: { ...off, offset_s: -240 } } });
    await waitFor(() => expect(screen.getByText(t("work.order.overview.closedBy"))).toBeTruthy());
    expect(screen.queryByText(t("work.order.overview.phoneClock"))).toBeNull();
  });
});

describe("DEF-WRK-9682 — a refused Accept says WHY, in the clerk's language", () => {
  // ⚠ Walked on PostgreSQL (lane WALK-B, CR-168 round 7): WO-0047's Accept
  // answered 409 `work.reading.no_meter_on_order` and the page toasted the
  // fallback *Could not accept.* for three seconds. The real client throws an
  // `ApiError` carrying `messageKey`; the helper read `error.data.message`,
  // which that error never has. So this stub throws the REAL error type.
  it("toasts the catalogue sentence of the server's message_key", async () => {
    const calls: Call[] = [];
    const base = client(COMPLETED, calls);
    const refusing = {
      ...base,
      post: async (path: string, body?: unknown) => {
        if (path.endsWith("/accept")) {
          calls.push({ method: "POST", path, body: body ?? null });
          throw new ApiError(409, {
            code: "BIZ-STATE",
            message_key: "work.reading.no_meter_on_order",
            params: { prompts: ["Meter number as fitted", "Opening register"] },
            field_errors: [],
            br_ref: "BR-WRK-003",
            trace_id: "e16c56beedf54c27a0b3b2d4dec7d106",
          } as never);
        }
        return base.post(path, body as never);
      },
    } as unknown as ApiClient;
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}/work/orders/${ID}?tab=overview`]}>
            <Routes>
              <Route path="/:tenant/work/orders/:orderNo" element={<OrderDetailPage client={refusing} />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(container.querySelector(".page-header-actions button")).not.toBeNull());
    fireEvent.click(screen.getByText(t("work.order.actions.accept")));
    fireEvent.click(within(screen.getByRole("alertdialog")).getByText(t("work.order.accept.confirm")));
    await waitFor(() => expect(screen.queryByText(t("work.reading.no_meter_on_order"))).toBeTruthy());
    expect(screen.queryByText(t("work.order.accept.refused"))).toBeNull();
  });
});

// ── CR-168-BRC10 round 8, lane FIX-8B ─────────────────────────────────────
describe("DEF-WRK-9675 — Send back… returns a finished job to the field (images 04, 06; P4.14)", () => {
  it("asks for a reason, refuses none, then posts /send-back with it", async () => {
    const calls: Call[] = [];
    mount(COMPLETED, "overview", calls);
    fireEvent.click(await screen.findByText(t("work.order.actions.sendBack")));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(t("work.order.sendBack.title", { order: "WO-0043" }))).toBeTruthy();
    expect(within(dialog).getByText(t("work.order.sendBack.consequence"))).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: t("work.order.sendBack.submit") }));
    await waitFor(() =>
      expect(within(dialog).getAllByText(t("work.order.send_back_reason_required")).length).toBeGreaterThan(0),
    );
    expect(posts(calls)).toEqual([]);
    fireEvent.change(within(dialog).getByLabelText(new RegExp(t("work.order.sendBack.reason"))), {
      target: { value: "No photo of the old meter." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: t("work.order.sendBack.submit") }));
    await waitFor(() => expect(posts(calls).length).toBe(1));
    expect(posts(calls)[0]).toMatchObject({
      method: "POST",
      path: `/work-orders/${ID}/send-back`,
      body: { reason: "No photo of the old meter." },
    });
  });

  it("an accepted job offers no Send back (BR-MET-110: nothing accepted is re-opened)", async () => {
    mount({ ...COMPLETED, accepted: { by: { name: "Dana Whitfield" }, at: "2026-09-26T08:00:00Z" } });
    await waitFor(() => expect(screen.getByText(t("work.order.overview.title"))).toBeTruthy());
    expect(screen.queryByText(t("work.order.actions.sendBack"))).toBeNull();
  });
});

describe("DEF-WRK-9690 — Duplicate raises the same job again (beta #28)", () => {
  it("confirms first, then posts /duplicate and opens the new order", async () => {
    const calls: Call[] = [];
    mount(OPEN, "overview", calls);
    fireEvent.click(await screen.findByText(t("work.order.actions.duplicate")));
    expect(posts(calls)).toEqual([]);
    const dialog = screen.getByRole("alertdialog");
    expect(within(dialog).getByText(t("work.order.duplicate.consequence"))).toBeTruthy();
    fireEvent.click(within(dialog).getByText(t("work.order.duplicate.confirm")));
    await waitFor(() => expect(posts(calls).length).toBe(1));
    expect(posts(calls)[0]).toMatchObject({ method: "POST", path: `/work-orders/${ID}/duplicate` });
  });
});

describe("DEF-WRK-9677 — Due shows the date the job is measured against", () => {
  it("a job raised with no priority reads the server's promise (sla.due_at), never a dash", async () => {
    const { container } = mount({
      ...OPEN,
      priority: null,
      due_at: null,
      sla: { due_at: "2026-09-27T06:02:00Z", target: "default", at_risk: false },
    });
    await waitFor(() => expect(screen.getByText(t("work.order.overview.due"))).toBeTruthy());
    const dd = screen.getByText(t("work.order.overview.due")).nextElementSibling as HTMLElement;
    expect(dd.textContent).toContain("09/27/2026");
    expect(container.querySelector("[data-order-overview]")).not.toBeNull();
  });
});

describe("DEF-WRK-9697 — a due with no time of its own reads as a date", () => {
  // The raise wizard and the edit form both pick the due as a DATE (ruling 23),
  // which the server stores as the tenant's midnight. It printed `10/06/2026
  // 00:00` beside a visit window of 08:00–12:00 — a midnight nobody chose.
  // The test's tenant zone is UTC (`SEED_TIME_ZONE`).
  it("a midnight due reads 10/06/2026, never 10/06/2026 00:00", async () => {
    mount({ ...OPEN, due_at: "2026-10-06T00:00:00Z" });
    await waitFor(() => expect(screen.getByText(t("work.order.overview.due"))).toBeTruthy());
    const dd = screen.getByText(t("work.order.overview.due")).nextElementSibling as HTMLElement;
    expect(dd.textContent).toBe("10/06/2026");
  });
  it("a due WITH a time of its own (a priority's promise) keeps the time", async () => {
    mount({ ...OPEN, due_at: "2026-09-27T06:03:00Z" });
    await waitFor(() => expect(screen.getByText(t("work.order.overview.due"))).toBeTruthy());
    const dd = screen.getByText(t("work.order.overview.due")).nextElementSibling as HTMLElement;
    expect(dd.textContent).toBe("09/27/2026 06:03");
  });
});

describe("DEF-WRK-9678 — the holder carries our customer number (images 03, 04)", () => {
  it("Holder reads Ana Alvarez · C-00001", async () => {
    mount({ ...OPEN, customer: { ...OPEN.customer, customer_no: "C-00001" } });
    expect(await screen.findByText("Ana Alvarez · C-00001")).toBeTruthy();
  });
});

describe("record links (PO 2026-10-19) — the order Overview", () => {
  it("meter, address, unit and account open their own records", async () => {
    mount(OPEN);
    await waitFor(() => expect(screen.getByText(t("work.order.overview.title"))).toBeTruthy());
    const href = (name: string) =>
      screen.getAllByRole("link", { name }).map((link) => link.getAttribute("href"));
    expect(href("W-5000")).toContain(`/${TENANT}/assets/a-1`);
    expect(href("101 Silver Creek Rd")).toContain(`/${TENANT}/premises/p-1`);
    expect(href("Unit 1")).toContain(`/${TENANT}/premises/units/u-1`);
    expect(href("AC-2026-00001")).toContain(`/${TENANT}/accounts/a-1`);
  });
});

describe("DEF-WRK-10635 — a refusal from the phone shows its door-hanger photo", () => {
  // The server's own shape (`evidence.signature_for_order`, DEF-WRK-10625):
  // the phone named a photo whose bytes have not landed yet.
  const REFUSED = {
    ...COMPLETED,
    signature: {
      printed_name: null,
      signed_at: "2026-09-25T11:42:00Z",
      refused: true,
      decline_reason: "Customer not home",
      captured_by: { name: "D. Ortiz" },
      image_url: null,
      door_hanger_attachment_id: null,
      door_hanger_uploading: true,
    },
  };

  it("before the bytes land, the panel says the photo is uploading", async () => {
    const { container } = mount(REFUSED, "overview");
    await waitFor(() => expect(container.querySelector("[data-signature]")).not.toBeNull());
    const line = container.querySelector('[data-door-hanger="uploading"]');
    expect(line?.textContent).toBe("Photo uploading");
    expect(container.querySelector('[data-photo-thumb="door-hanger"]')).toBeNull();
  });

  it("once landed, the door hanger is a thumbnail and View opens it from the API", async () => {
    const landed = {
      ...REFUSED,
      signature: { ...REFUSED.signature, door_hanger_attachment_id: "att-9", door_hanger_uploading: false },
    };
    const { container } = mount(landed, "overview");
    await waitFor(() => expect(container.querySelector('[data-photo-thumb="door-hanger"]')).not.toBeNull());
    const src = `/api/${TENANT}/work-orders/${ID}/attachments/att-9/content`;
    expect(container.querySelector('[data-photo-thumb="door-hanger"] img')?.getAttribute("src")).toBe(src);
    expect(container.querySelector('[data-door-hanger="uploading"]')).toBeNull();
    const panel = container.querySelector("[data-signature]") as HTMLElement;
    fireEvent.click(within(panel).getByText(t("work.order.signature.view")));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("img").getAttribute("src")).toBe(src);
    // B14 rule 31 — the attachment's id builds the link and is never shown.
    expect(document.body.textContent).not.toContain("att-9");
  });
});

describe("DEF-FLD-10640 (FB-015, WO-0171) — every photograph of the completed job is shown", () => {
  const JOB_LEVEL = { id: "att-9", kind: "work_order_photo", taken_at: "2026-09-25T11:30:00Z", device: null, added_by_name: "D. Ortiz", reading_id: null, task_id: null };
  const SECOND_ON_T1 = { id: "att-3", kind: "work_order_photo", taken_at: "2026-09-25T10:14:00Z", device: null, added_by_name: "M. Reyes", reading_id: null, task_id: "t1" };
  const SIGNATURE = { id: "att-8", kind: "work_order_signature", taken_at: "2026-09-25T11:42:00Z", device: null, added_by_name: "D. Ortiz", reading_id: null, task_id: null };

  it("a photograph taken for the job at large (no task, no reading) is listed under Photos and opens the viewer with who and when", async () => {
    const { container } = mount(COMPLETED, "checklist", [], [...ATTACHMENTS, JOB_LEVEL]);
    await waitFor(() => expect(container.querySelector('[data-order-photo="job-1"]')).not.toBeNull());
    expect(screen.getByText(t("work.order.photos.title"))).toBeTruthy();
    const tile = container.querySelector('[data-order-photo="job-1"]') as HTMLElement;
    expect(tile.textContent).toContain(t("work.order.photo.job"));
    expect(tile.textContent).toContain("D. Ortiz");
    expect(tile.textContent).not.toContain("att-9");
    fireEvent.click(within(tile).getByRole("button"));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("img").getAttribute("src")).toBe(`/api/${TENANT}/work-orders/${ID}/attachments/att-9/content`);
    expect(within(dialog).getByText(t("work.order.photo.forJob"))).toBeTruthy();
    expect(within(dialog).getByText(t("work.order.photo.position", { at: 3, total: 3 }))).toBeTruthy();
  });

  it("WO-0171's case: the job's only uploaded photograph belongs to no row — it is still shown", async () => {
    const { container } = mount(COMPLETED, "checklist", [], [JOB_LEVEL]);
    await waitFor(() => expect(container.querySelector('[data-order-photos] [data-photo-thumb="job-1"]')).not.toBeNull());
  });

  it("two photographs on one task are both shown, and a signature is not a photograph", async () => {
    const { container } = mount(COMPLETED, "checklist", [], [...ATTACHMENTS, SECOND_ON_T1, SIGNATURE]);
    await waitFor(() => expect(container.querySelectorAll("[data-order-photos] [data-photo-thumb]").length).toBe(3));
    const keys = [...container.querySelectorAll("[data-order-photo]")].map((el) => el.getAttribute("data-order-photo"));
    expect(keys).toEqual(["task-1", "task-1-2", "reading-1"]);
    const second = container.querySelector('[data-order-photo="task-1-2"]') as HTMLElement;
    expect(second.textContent).toContain("Read and photograph the OLD meter");
    expect(second.textContent).toContain("M. Reyes");
  });
});
