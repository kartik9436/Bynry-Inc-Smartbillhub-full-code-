// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-193-BRC10 — MQ-040 STEP 1 (decision log 2026-10-26): Working
//           days and Exceptions on the technician's Overview, and the
//           Timesheets tab.
// Shapes:   the server's answers as `apps/work/shifts.py` builds them
//           (`tests/test_cr193_shifts.py` asserts them on the server); the
//           technician is the recording `__fixtures__/server/work.technician.json`.
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";
import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { TechnicianDetailPage } from "./TechnicianDetailPage";
import TECHNICIAN from "./__fixtures__/server/work.technician.json";
import JOBS_OPEN from "./__fixtures__/server/work.technician.jobs.open.json";

const TENANT = "brazosbend";
const SLUG = TECHNICIAN.slug;
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params as never) as unknown as string;

const EXCEPTION = { id: "019a1111-0000-7000-8000-000000000001", date: "2026-10-27", kind: "off", start: null, end: null, note: "Dentist" };
const SUBMITTED = {
  date: "2026-10-23",
  jobs: 2,
  labour_minutes: 99,
  travel_minutes: 14,
  lines: [{ order_id: "019a2222-0000-7000-8000-000000000002", order_no: "WO-4822", labour_minutes: 72, travel_minutes: 14 }],
  submitted_at: "2026-10-23T22:10:00Z",
};

const page = <T,>(rows: T[]) => ({ count: rows.length, next: null, previous: null, results: rows });
const ok = (data: unknown): ApiResponse<unknown> => ({ status: 200, data, etag: null, notModified: false });

function server() {
  const writes: { verb: string; path: string; body?: unknown }[] = [];
  let weekdays = ["mon", "tue", "wed", "thu", "fri"];
  const get = async (path: string): Promise<ApiResponse<unknown>> => {
    if (path.endsWith("/working-days")) return ok({ weekdays, is_default: true, shift_start: "07:00", shift_end: "15:30" });
    if (path.endsWith("/exceptions")) return ok(page([EXCEPTION]));
    if (path.endsWith("/timesheets")) return ok(page([SUBMITTED]));
    if (path.endsWith("/devices")) return ok(page([]));
    if (path.endsWith("/jobs")) return ok(JOBS_OPEN);
    return ok(TECHNICIAN);
  };
  const put = async (path: string, body: unknown) => {
    writes.push({ verb: "PUT", path, body });
    weekdays = (body as { weekdays: string[] }).weekdays;
    return ok({ weekdays, is_default: false, shift_start: "07:00", shift_end: "15:30" });
  };
  const post = async (path: string, body: unknown) => {
    writes.push({ verb: "POST", path, body });
    return { ...ok({ ...EXCEPTION, ...(body as object), id: "019a1111-0000-7000-8000-000000000009" }), status: 201 };
  };
  const patch = async (path: string, body: unknown) => {
    writes.push({ verb: "PATCH", path, body });
    return ok({ ...EXCEPTION, ...(body as object) });
  };
  const del = async (path: string) => {
    writes.push({ verb: "DELETE", path });
    return { status: 204, data: null, etag: null, notModified: false };
  };
  return { client: { get, put, post, patch, del } as unknown as ApiClient, writes };
}

function mount(client: ApiClient, tab?: string) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/work/crews/${SLUG}${tab ? `?tab=${tab}` : ""}`]}>
          <Routes>
            <Route path="/:tenant/work/crews/:slug" element={<TechnicianDetailPage client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => cleanup());

describe("CR-193 — Working days on the technician's Overview", () => {
  it("shows the seven days, Monday to Friday on, and the shift window", async () => {
    mount(server().client);
    const panel = (await screen.findByText(t("work.technician.workingDays.title"))).closest("section") as HTMLElement;
    const days = await within(panel).findAllByRole("button", { pressed: true });
    expect(days.map((b) => b.textContent)).toEqual(["mon", "tue", "wed", "thu", "fri"].map((d) => t(`work.technician.workingDays.day.${d}`)));
    expect(within(panel).getAllByRole("button", { pressed: false })).toHaveLength(2);
    expect(within(panel).getByText(t("work.technician.workingDays.window", { start: "07:00", end: "15:30" }))).toBeTruthy();
  });

  it("pressing Saturday saves the whole set, Monday first", async () => {
    const { client, writes } = server();
    mount(client);
    fireEvent.click(await screen.findByRole("button", { name: t("work.technician.workingDays.day.sat"), pressed: false }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toEqual({
      verb: "PUT",
      path: `/work/technicians/${SLUG}/working-days`,
      body: { weekdays: ["mon", "tue", "wed", "thu", "fri", "sat"] },
    });
  });
});

describe("CR-193 — Exceptions on the technician's Overview", () => {
  it("lists a day off with its note, and no id on screen", async () => {
    mount(server().client);
    const panel = (await screen.findByText(t("work.technician.exceptions.title"))).closest("section") as HTMLElement;
    const row = await within(panel).findByText("Dentist");
    expect(row.closest("tr")?.textContent).toContain(t("work.technician.exceptions.kind.off"));
    expect(panel.textContent).not.toContain(EXCEPTION.id);
  });

  it("adds a day with different hours through our form", async () => {
    const { client, writes } = server();
    mount(client);
    fireEvent.click(await screen.findByText(t("work.technician.exceptions.add")));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(new RegExp(`^${t("work.technician.exceptions.field.date")}`, "u")), { target: { value: "2026-11-02" } });
    fireEvent.click(within(dialog).getByRole("radio", { name: t("work.technician.exceptions.kind.window") }));
    fireEvent.change(within(dialog).getByLabelText(t("work.crews.shift.from")), { target: { value: "06:00" } });
    fireEvent.change(within(dialog).getByLabelText(t("work.crews.shift.until")), { target: { value: "10:00" } });
    fireEvent.click(within(dialog).getByText(t("work.technician.exceptions.save")));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toEqual({
      verb: "POST",
      path: `/work/technicians/${SLUG}/exceptions`,
      body: { date: "2026-11-02", kind: "window", start: "06:00", end: "10:00", note: "" },
    });
  });

  it("removes a day only after the danger confirm", async () => {
    const { client, writes } = server();
    mount(client);
    const panel = (await screen.findByText(t("work.technician.exceptions.title"))).closest("section") as HTMLElement;
    await within(panel).findByText("Dentist");
    fireEvent.click(within(panel).getByRole("button", { name: t("work.technician.exceptions.remove") }));
    expect(writes).toHaveLength(0);
    fireEvent.click(await screen.findByText(t("work.technician.exceptions.removeConfirm")));
    await waitFor(() => expect(writes).toEqual([{ verb: "DELETE", path: `/work/technicians/${SLUG}/exceptions/${EXCEPTION.id}` }]));
  });
});

describe("CR-193 — the Timesheets tab", () => {
  it("is a tab of the technician's page", async () => {
    mount(server().client);
    expect(await screen.findByRole("tab", { name: t("work.technician.tab.timesheets") })).toBeTruthy();
  });

  it("lists each submitted day: jobs, on site, travel — no ids", async () => {
    mount(server().client, "timesheets");
    const table = (await screen.findByText(t("work.technician.timesheets.col.onSite"))).closest("table") as HTMLElement;
    const cells = within(table).getAllByRole("cell").map((c) => c.textContent);
    expect(cells).toContain("2");
    expect(cells).toContain("1h 39m");
    expect(cells).toContain("14m");
    expect(table.textContent).not.toContain(SUBMITTED.lines[0]!.order_id);
  });
});
