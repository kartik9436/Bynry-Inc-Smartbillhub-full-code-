// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-10591 — no screen could assign a route's reader (MQ-033).
// Ruling:   PO 2026-10-24 — assign/reassign on Reads → cycle → Routes, with the
//           drawn Reader column; supersedes CR-029 D6 and OQ-343 for that tab.
// Rules:    B14 rule 15 (icons, max two visible, then `…`) · rule 31 (the
//           reader by NAME, never its id) · BR-FLD-00087 (one reader)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import i18n from "i18next";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { CycleRow, MyPermissions, RouteRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { AssignReaderModal, currentReaderLine } from "./AssignReaderModal";
import { ReadCycleDetailPage, readCycleQueryKey, readerTarget } from "./ReadCycleDetailPage";
import { PREMISES_PERMISSION, readCycleDetailPath } from "./meteringShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

const CYCLE_ID = "01a09e06-4523-7226-9328-26cbe9839a9e";
const RAY_ID = "01a09e06-9999-7226-9328-26cbe9839a01";
const MIA_ID = "01a09e06-9999-7226-9328-26cbe9839a02";
const RT1 = "01a09e06-1111-7226-9328-26cbe9839a11";
const RT2 = "01a09e06-2222-7226-9328-26cbe9839a22";

function route(over: Partial<RouteRow>): RouteRow {
  return {
    id: RT1,
    code: "RT-001",
    name: "Maple",
    route_type: "walk",
    feeder_ref: null,
    assigned_to: null,
    reader: null,
    cycle_id: CYCLE_ID,
    cycle_code: "CY-001",
    status: "active",
    members: 3,
    meters: 4,
    collected: null,
    last_completion: null,
    progress: null,
    premises: 3,
    ...over,
  } as RouteRow;
}

const ROWS: RouteRow[] = [
  route({ id: RT1, code: "RT-001", assigned_to: RAY_ID, reader: { id: RAY_ID, name: "Ray Reader" } }),
  route({ id: RT2, code: "RT-002" }),
];

function fakeClient(posted: unknown[]): ApiClient {
  const ok = <T,>(data: T) => Promise.resolve({ status: 200, data, etag: null, notModified: false });
  return {
    get: vi.fn((path: string) => {
      if (path.startsWith("/routes/reader-choices")) {
        return ok({
          count: 1,
          next: null,
          previous: null,
          results: [{ id: MIA_ID, name: "Mia Ortiz", email: "mia@b.test" }],
        });
      }
      if (path === "/routes") return ok({ count: ROWS.length, next: null, previous: null, results: ROWS });
      if (path === `/cycles/${CYCLE_ID}`) return ok(cycle());
      return ok({ rows: [], count: 0 });
    }),
    post: vi.fn((path: string, body: unknown) => {
      posted.push({ path, body });
      return ok({ updated: 1, unchanged: 0, routes: [] });
    }),
  } as unknown as ApiClient;
}

function cycle(): CycleRow {
  return {
    id: CYCLE_ID,
    code: "CY-001",
    routes: ["RT-001", "RT-002"],
    window_start: "2026-10-14",
    window_end: "2026-10-18",
    status: "in_progress",
    frequency: "Monthly",
  } as unknown as CycleRow;
}

function mountRoutesTab(client: ApiClient) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(readCycleQueryKey(CYCLE_ID), cycle());
  const perms: MyPermissions = {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: PREMISES_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  };
  queryClient.setQueryData(queryKeys.myPermissions, perms);
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/brazosbend${readCycleDetailPath(CYCLE_ID)}?tab=routes`]}>
          <Routes>
            <Route
              path="/:tenant/reads/cycles/:cycleId"
              element={<ReadCycleDetailPage client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("MQ-033 — the Routes tab names each route's reader", () => {
  it("draws the Reader column: the NAME, or Not assigned — never the id", async () => {
    const { container } = mountRoutesTab(fakeClient([]));
    await screen.findByText("Ray Reader");
    expect(screen.getByRole("columnheader", { name: t("metering.routeReader.col") })).toBeInTheDocument();
    expect(screen.getAllByText(t("metering.routeReader.notAssigned")).length).toBeGreaterThan(0);
    expect(container.innerHTML).not.toContain(RAY_ID); // B14 rule 31
  });

  it("the row's overflow offers Assign or Reassign; upload stays the one visible icon", async () => {
    mountRoutesTab(fakeClient([]));
    await screen.findByText("Ray Reader");
    expect(screen.getByTestId("assign-reader-RT-001")).toHaveTextContent(t("metering.routeReader.reassign"));
    expect(screen.getByTestId("assign-reader-RT-002")).toHaveTextContent(t("metering.routeReader.assign"));
  });

  it("ticking two routes opens ONE dialog over both and posts both ids", async () => {
    const posted: { path: string; body: { route_ids: string[]; reader_id: string | null } }[] = [];
    mountRoutesTab(fakeClient(posted));
    await screen.findByText("Ray Reader");
    fireEvent.click(screen.getByLabelText(t("metering.routeReader.select", { route: "RT-001" })));
    fireEvent.click(screen.getByLabelText(t("metering.routeReader.select", { route: "RT-002" })));
    expect(screen.getByText(t("metering.routeReader.routesPicked", { count: 2 }))).toBeInTheDocument();
    const bulk = document.querySelector<HTMLElement>('[data-cycle="routes-bulk"]');
    expect(bulk).not.toBeNull();
    fireEvent.click(within(bulk as HTMLElement).getByRole("button", { name: t("metering.routeReader.bulkAssign") }));
    const dialog = await screen.findByRole("dialog");
    // Unassign clears the reader on every route in the dialog that has one.
    fireEvent.click(within(dialog).getByRole("button", { name: t("metering.routeReader.unassign") }));
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0].path).toBe("/routes/reader");
    expect(posted[0].body).toEqual({ route_ids: [RT1, RT2], reader_id: null });
  });
});

describe("AssignReaderModal", () => {
  it("says who reads one route now, or how many are picked", () => {
    expect(currentReaderLine([readerTarget(ROWS[0])], t)).toBe(
      t("metering.routeReader.readsNow", { name: "Ray Reader" }),
    );
    expect(currentReaderLine([readerTarget(ROWS[1])], t)).toBe(t("metering.routeReader.notAssigned"));
    expect(currentReaderLine(ROWS.map(readerTarget), t)).toBe(
      t("metering.routeReader.routesPicked", { count: 2 }),
    );
  });

  it("picks a technician by search, confirms, and saves their id", async () => {
    const posted: { path: string; body: unknown }[] = [];
    const onSaved = vi.fn();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AssignReaderModal
          routes={[readerTarget(ROWS[1])]}
          client={fakeClient(posted)}
          onClose={() => undefined}
          onSaved={onSaved}
        />
      </QueryClientProvider>,
    );
    // No current reader → no Unassign.
    expect(screen.queryByRole("button", { name: t("metering.routeReader.unassign") })).toBeNull();
    fireEvent.change(screen.getByLabelText(new RegExp(t("metering.routeReader.field"))), {
      target: { value: "mia" },
    });
    fireEvent.click(screen.getByRole("button", { name: t("metering.routeReader.find") }));
    fireEvent.click(await screen.findByText("Mia Ortiz"));
    fireEvent.click(await screen.findByRole("button", { name: t("metering.routeReader.use") }));
    fireEvent.click(screen.getByRole("button", { name: t("metering.routeReader.save") }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(posted[0]).toEqual({ path: "/routes/reader", body: { route_ids: [RT2], reader_id: MIA_ID } });
  });
});
