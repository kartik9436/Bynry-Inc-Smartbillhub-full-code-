// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 §30, lane BOARDS — the daily job limit on the
//           technician's page. PO answer (2), 2026-10-05, verbatim: *"(b) Add a
//           daily limit per technician (default 6), editable on the
//           technician's page."*
// Shapes:   the technician is the RECORDING `__fixtures__/server/
//           work.technician.json` (made before 2.519.0) with the one new field
//           `daily_job_limit` the server now serves beside it
//           (`tests/test_cr168_boards_lane.py` asserts it on the server).
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";
import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { TechnicianDetailPage } from "./TechnicianDetailPage";
import type { TechnicianDetail } from "./workEndpoints";
import TECHNICIAN from "./__fixtures__/server/work.technician.json";
import JOBS_OPEN from "./__fixtures__/server/work.technician.jobs.open.json";

const TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params as never) as unknown as string;

function server(limit: number) {
  const patches: { path: string; body: unknown }[] = [];
  let detail = { ...(TECHNICIAN as unknown as TechnicianDetail), daily_job_limit: limit };
  const get = async (path: string): Promise<ApiResponse<unknown>> => {
    const data = path.endsWith("/jobs") ? JOBS_OPEN : detail;
    return { status: 200, data, etag: null, notModified: false };
  };
  const patch = async (path: string, body: unknown): Promise<ApiResponse<unknown>> => {
    patches.push({ path, body });
    detail = { ...detail, daily_job_limit: (body as { daily_job_limit: number }).daily_job_limit };
    return { status: 200, data: detail, etag: null, notModified: false };
  };
  return { client: { get, patch, post: patch } as unknown as ApiClient, patches };
}

function mount(client: ApiClient) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/work/crews/${TECHNICIAN.slug}`]}>
          <Routes>
            <Route path="/:tenant/work/crews/:slug" element={<TechnicianDetailPage client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => cleanup());

describe("§30 — the daily job limit on the technician's page", () => {
  it("reads the server's limit on the Overview — 6 jobs a day by default", async () => {
    mount(server(6).client);
    expect(await screen.findByText(t("work.technician.dailyLimit.value", { count: 6 }))).toBeTruthy();
    expect(screen.getByText(t("work.technician.dailyLimit.title"))).toBeTruthy();
  });

  it("Edit opens our form; Save sends ONE patch with the whole number", async () => {
    const { client, patches } = server(6);
    mount(client);
    fireEvent.click(await screen.findByText(t("work.technician.dailyLimit.edit")));
    const input = (await screen.findByRole("textbox", { name: new RegExp(`^${t("work.technician.dailyLimit.title")}`, "u") })) as HTMLInputElement;
    expect(input.value).toBe("6");
    fireEvent.change(input, { target: { value: "8" } });
    fireEvent.click(screen.getByText(t("work.technician.dailyLimit.save")));
    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0]).toEqual({ path: `/work/technicians/${TECHNICIAN.slug}`, body: { daily_job_limit: 8 } });
  });

  it("refuses a limit that is not a whole number of one or more, before sending", async () => {
    const { client, patches } = server(6);
    mount(client);
    fireEvent.click(await screen.findByText(t("work.technician.dailyLimit.edit")));
    const input = (await screen.findByRole("textbox", { name: new RegExp(`^${t("work.technician.dailyLimit.title")}`, "u") })) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "0" } });
    fireEvent.click(screen.getByText(t("work.technician.dailyLimit.save")));
    expect(await screen.findAllByText(t("work.technician.daily_limit_invalid"))).not.toHaveLength(0);
    expect(patches).toHaveLength(0);
  });
});
