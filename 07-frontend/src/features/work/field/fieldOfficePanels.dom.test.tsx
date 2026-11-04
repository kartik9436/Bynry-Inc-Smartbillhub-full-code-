// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Stories:  US-WRK-059 (the order's outcome and come-backs) · US-WRK-057
//           (*Send alert…* on an order) · US-WRK-058 (a technician's
//           handsets and the office's sign-out) — EP-WRK-11
// Rules:    BR-FLD-00004 · E2E-04 · E2E-17/18 · BR-FLD-00029 · R113 · R115 ·
//           B14 rules 6 (danger tier, asked first) · 31 (no id shown)
// ───────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { ToastProvider } from "@/components/Toast";

import type { ComeBackHistory, OrderOutcome, TechnicianDeviceRow } from "./fieldDeskEndpoints";
import { OrderFieldPanels } from "./OrderFieldPanels";
import { SendAlertDialog } from "./SendAlertDialog";
import { TechnicianDevicesPanel } from "./TechnicianDevicesPanel";
import { commits, fakeClient } from "./fieldTestClient";
import type { Call } from "./fieldTestClient";

const TENANT = "brazosbend";
const ORDER_ID = "0b6f2c1e-1111-4a4a-9c9c-000000004903";

afterEach(cleanup);

/** The *From the field* group is closed by default (its reads run on open). */
function openGroup() {
  fireEvent.click(screen.getByRole("button", { name: /From the field/ }));
}

function frame(children: ReactNode, address = `/${TENANT}/work/orders/WO-4903`, pattern = "/:tenant/work/orders/:orderNo") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[address]}>
          <Routes>
            <Route path={pattern} element={children} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const OUTCOME: OrderOutcome = {
  id: ORDER_ID,
  order_no: "WO-4903",
  outcome: "partially_done",
  word: "partly_done",
  kind: "partial",
  is_failure: false,
  reason: "Ran out of seals",
  reason_missing: false,
  blocker: null,
  blocker_known: null,
  steps_done: 3,
  steps_total: 5,
  remaining_steps: [
    { seq: 4, title: "Seal the meter", is_mandatory: true },
    { seq: 5, title: "Photo of the seal", is_mandatory: false },
  ],
  photographs: 4,
  completed_at: "2026-10-20T15:40:00Z",
  accepted_at: null,
  cost: { frozen: false, report_version: null, total: "138.42" },
};

const HISTORY: ComeBackHistory = {
  order_id: ORDER_ID,
  order_no: "WO-4903",
  followed_on_from: { id: "0b6f2c1e-1111-4a4a-9c9c-000000004800", order_no: "WO-4800" },
  events: [
    {
      id: "e1",
      kind: "technician_reopen",
      reason: "missed_step",
      note: null,
      at: "2026-10-20T16:00:00Z",
      by: "D. Ortiz",
      follow_on: null,
    },
    {
      id: "e2",
      kind: "follow_on",
      reason: "Second visit for the seal",
      note: "Bring seals",
      at: "2026-10-21T09:00:00Z",
      by: "A. Reed",
      follow_on: { id: "0b6f2c1e-1111-4a4a-9c9c-000000005001", order_no: "WO-5001" },
    },
  ],
};

describe("US-WRK-059 — the order says what the field said, and every time it came back", () => {
  it("TC-1 — a completed job draws its outcome, its reason, the steps a partial left, photos and cost", async () => {
    const calls: Call[] = [];
    const client = fakeClient(calls, {
      [`/work-orders/${ORDER_ID}/outcome`]: OUTCOME,
      [`/work-orders/${ORDER_ID}/come-backs`]: HISTORY,
    });
    frame(<OrderFieldPanels orderId={ORDER_ID} completed client={client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />);
    openGroup();
    await waitFor(() => expect(screen.getByText("Field outcome")).toBeInTheDocument());
    const panel = document.querySelector("[data-order-field-outcome]") as HTMLElement;
    expect(within(panel).getByText("Partly done")).toBeInTheDocument();
    expect(within(panel).getByText("Ran out of seals")).toBeInTheDocument();
    expect(within(panel).getByText("3 of 5")).toBeInTheDocument();
    expect(within(panel).getByText("Seal the meter")).toBeInTheDocument();
    expect(within(panel).getByText("Photo of the seal")).toBeInTheDocument();
    expect(within(panel).getByText("$138.42")).toBeInTheDocument();
    expect(within(panel).getByText("Preview")).toBeInTheDocument();
  });

  it("FB-013 — a paid close reads Not done — payment received, with the remark, the times and the money seen", async () => {
    const calls: Call[] = [];
    const paid: OrderOutcome = {
      ...OUTCOME,
      outcome: "not_done_payment_received",
      word: "not_done_paid",
      kind: "paid",
      reason: "Customer has paid. Not disconnected.",
      remaining_steps: [],
      times: { arrived_at: "2026-10-20T15:30:00Z", finished_at: "2026-10-20T15:40:00Z" },
      payment_received: {
        phone: {
          balance: "0.0000",
          currency: "USD",
          as_at: "2026-10-20T15:32:00Z",
          checked_at: "2026-10-20T15:33:00Z",
          latest_payment: { amount: "312.4000", at: "2026-10-20T14:05:00Z" },
        },
        server: {
          as_at: "2026-10-20T15:41:00Z",
          owing: { amount: "0.0000", display: "0.00", currency: "USD" },
          balance: { amount: "0.0000", display: "0.00", currency: "USD" },
          currency: "USD",
          latest_payment: null,
          unavailable: [],
        },
        fresh_minutes: 5,
        task_title: "Close the valve",
      },
    };
    const client = fakeClient(calls, {
      [`/work-orders/${ORDER_ID}/outcome`]: paid,
      [`/work-orders/${ORDER_ID}/come-backs`]: HISTORY,
    });
    frame(<OrderFieldPanels orderId={ORDER_ID} completed client={client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />);
    openGroup();
    await waitFor(() => expect(screen.getByText("Field outcome")).toBeInTheDocument());
    const panel = document.querySelector("[data-order-field-outcome]") as HTMLElement;
    expect(within(panel).getByText("Not done — payment received")).toBeInTheDocument();
    expect(within(panel).getByText("Customer has paid. Not disconnected.")).toBeInTheDocument();
    expect(within(panel).getByText("Times")).toBeInTheDocument();
    expect(within(panel).getByText("Balance seen")).toBeInTheDocument();
    expect(within(panel.querySelector("[data-paid-payment-seen]") as HTMLElement).getByText("$312.40")).toBeInTheDocument();
    expect(within(panel.querySelector("[data-paid-balance-seen]") as HTMLElement).getByText("$0.00")).toBeInTheDocument();
    expect(within(panel).getByText("Balance at close")).toBeInTheDocument();
    expect(within(panel.querySelector("[data-paid-balance-at-close]") as HTMLElement).getByText("$0.00")).toBeInTheDocument();
  });

  it("TC-2 — reopen and follow-on read differently; the follow-on's new order and the parent are links", async () => {
    const client = fakeClient([], {
      [`/work-orders/${ORDER_ID}/outcome`]: OUTCOME,
      [`/work-orders/${ORDER_ID}/come-backs`]: HISTORY,
    });
    frame(<OrderFieldPanels orderId={ORDER_ID} completed client={client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />);
    openGroup();
    await waitFor(() => expect(screen.getByText("Reopens and follow-ons")).toBeInTheDocument());
    const reopen = document.querySelector('[data-come-back="technician_reopen"]') as HTMLElement;
    expect(reopen.textContent).toContain("Reopened by technician");
    // A technician's reason is FF-36's word, in the clerk's language.
    expect(reopen.textContent).toContain("Missed a step");
    const follow = document.querySelector('[data-come-back="follow_on"]') as HTMLElement;
    expect(follow.textContent).toContain("Follow-on raised");
    expect(within(follow).getByRole("link", { name: "WO-5001" })).toHaveAttribute(
      "href",
      `/${TENANT}/work/orders/0b6f2c1e-1111-4a4a-9c9c-000000005001`,
    );
    expect(screen.getByRole("link", { name: "WO-4800" })).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(ORDER_ID);
  });

  it("TC-3 — an OPEN job never asks for an outcome, and a job that never came back draws nothing", async () => {
    const calls: Call[] = [];
    const client = fakeClient(calls, {
      [`/work-orders/${ORDER_ID}/come-backs`]: { ...HISTORY, followed_on_from: null, events: [] },
    });
    frame(<OrderFieldPanels orderId={ORDER_ID} completed={false} client={client} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />);
    openGroup();
    await waitFor(() => expect(calls.some((c) => c.path.endsWith("/come-backs"))).toBe(true));
    expect(calls.some((c) => c.path.endsWith("/outcome"))).toBe(false);
    expect(screen.queryByText("Field outcome")).not.toBeInTheDocument();
    expect(screen.queryByText("Reopens and follow-ons")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("No reopens or follow-ons yet.")).toBeInTheDocument());
  });

  it("TC-3b — CLOSED by default: nothing is read until a dispatcher opens the group", () => {
    const calls: Call[] = [];
    let alerted = false;
    frame(
      <OrderFieldPanels
        orderId={ORDER_ID}
        completed={false}
        client={fakeClient(calls, {})}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
        onAlert={() => {
          alerted = true;
        }}
      />,
    );
    expect(screen.getByRole("button", { name: /From the field/ })).toHaveAttribute("aria-expanded", "false");
    expect(calls).toHaveLength(0);
    // The group's action is *Send alert…*, beside the toggle — not in the drawn head.
    fireEvent.click(screen.getByRole("button", { name: "Send alert…" }));
    expect(alerted).toBe(true);
  });

  it("TC-3c — a job with nobody to ring offers no Send alert", () => {
    frame(<OrderFieldPanels orderId={ORDER_ID} completed client={fakeClient([], {})} timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />);
    expect(screen.queryByRole("button", { name: "Send alert…" })).not.toBeInTheDocument();
  });
});

describe("US-WRK-057 — Send alert… on an order", () => {
  it("TC-4 — sends the kind to the order, with a key minted at open", async () => {
    const calls: Call[] = [];
    let sent = false;
    frame(
      <SendAlertDialog
        orderId={ORDER_ID}
        orderNo="WO-4903"
        client={fakeClient(calls, { "POST /work/field-alerts": { id: "al-9" } })}
        onClose={() => undefined}
        onSent={() => {
          sent = true;
        }}
      />,
    );
    fireEvent.change(document.getElementById("kind") as HTMLSelectElement, { target: { value: "emergency" } });
    fireEvent.click(screen.getByRole("button", { name: /Send ✓/ }));
    await waitFor(() => expect(commits(calls)).toHaveLength(1));
    expect(commits(calls)[0].path).toBe("/work/field-alerts");
    expect(commits(calls)[0].body).toMatchObject({ kind: "emergency", work_order_id: ORDER_ID });
    expect(typeof (commits(calls)[0].body as { key?: unknown }).key).toBe("string");
    await waitFor(() => expect(sent).toBe(true));
  });

  it("TC-5 — a dispatch message needs its words (BR-FLD-00029)", async () => {
    const calls: Call[] = [];
    frame(
      <SendAlertDialog
        orderId={ORDER_ID}
        orderNo="WO-4903"
        client={fakeClient(calls, {})}
        onClose={() => undefined}
        onSent={() => undefined}
      />,
    );
    fireEvent.change(document.getElementById("kind") as HTMLSelectElement, { target: { value: "dispatch_message" } });
    fireEvent.click(screen.getByRole("button", { name: /Send ✓/ }));
    await waitFor(() => expect(screen.getByText("Write the message.")).toBeInTheDocument());
    expect(commits(calls)).toHaveLength(0);
  });
});

function device(over: Partial<TechnicianDeviceRow> = {}): TechnicianDeviceRow {
  return {
    device_id: "0b6f2c1e-4444-4a4a-9c9c-0000000000d1",
    device_uid: "HANDSET-UID-7f3a9",
    name: "Van 12 tablet",
    platform: "android",
    active: true,
    signed_out: false,
    signed_out_at: null,
    push_registered: true,
    last_four: "9a1c",
    registered_at: "2026-10-01T08:00:00Z",
    last_seen_at: "2026-10-21T13:55:00Z",
    ...over,
  };
}

function devicesPage(rows: TechnicianDeviceRow[]) {
  return { count: rows.length, next: null, previous: null, results: rows };
}

describe("US-WRK-058 — a technician's handsets, and signing one out", () => {
  const mountDevices = (calls: Call[], rows: TechnicianDeviceRow[]) =>
    frame(
      <TechnicianDevicesPanel
        slug="d-ortiz"
        client={fakeClient(calls, {
          "/work/technicians/d-ortiz/devices": devicesPage(rows),
          [`POST /work/technicians/d-ortiz/devices/${rows[0]?.device_id ?? "x"}/sign-out`]: { ...rows[0], signed_out: true },
        })}
        timeZone="America/Chicago"
        dateFormat="MM/DD/YYYY"
      />,
      `/${TENANT}/work/crews/d-ortiz`,
      "/:tenant/work/crews/:slug",
    );

  it("TC-6 — lists each handset by name, never by its identifier or push token", async () => {
    const calls: Call[] = [];
    mountDevices(calls, [device(), device({ device_id: "d2", name: null, platform: "ios", signed_out: true, push_registered: false })]);
    await waitFor(() => expect(screen.getByText("Van 12 tablet")).toBeInTheDocument());
    expect(calls[0].query).toMatchObject({ page: 1 });
    expect(screen.getByText("Unnamed device")).toBeInTheDocument();
    expect(screen.getByText("Android device")).toBeInTheDocument();
    expect(screen.getByText("iPhone or iPad")).toBeInTheDocument();
    expect(screen.getByText("Signed in")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("HANDSET-UID-7f3a9");
    expect(document.body.textContent).not.toContain("9a1c");
    expect(document.body.textContent).not.toContain(device().device_id);
  });

  it("TC-7 — Sign out asks first, in the danger tier, names what is kept, then posts to the handset's address", async () => {
    const calls: Call[] = [];
    mountDevices(calls, [device()]);
    await waitFor(() => expect(screen.getByText("Van 12 tablet")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Sign out Van 12 tablet" }));
    expect(commits(calls)).toHaveLength(0);
    expect(screen.getByText("Sign out Van 12 tablet?")).toBeInTheDocument();
    expect(screen.getByText("Everyone on it is signed out. Unsent work is kept.")).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "Sign out device" });
    expect(confirm.className).toMatch(/danger/);
    fireEvent.click(confirm);
    await waitFor(() => expect(commits(calls)).toHaveLength(1));
    expect(commits(calls)[0].path).toBe(`/work/technicians/d-ortiz/devices/${device().device_id}/sign-out`);
  });

  it("TC-8 — a handset already signed out offers no sign-out", async () => {
    mountDevices([], [device({ signed_out: true, active: false })]);
    await waitFor(() => expect(screen.getByText("Van 12 tablet")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Sign out Van 12 tablet" })).toBeDisabled();
  });

  it("TC-9 — no handsets says so", async () => {
    mountDevices([], []);
    await waitFor(() => expect(screen.getByText("No devices yet.")).toBeInTheDocument());
  });
});
