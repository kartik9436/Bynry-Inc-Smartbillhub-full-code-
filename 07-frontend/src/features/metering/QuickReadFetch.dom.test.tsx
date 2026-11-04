// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-10183 — Reads → Add reading had no Fetch. PO ruling
//           2026-10-17 (decision log "WHERE A USER ENTERS A METER READING",
//           gap 4), and the same day: "use same code components" — the box,
//           its date and Fetch are the shared `MeterReadingEntry`.
// Rules:    hard-won law 1 (the box is filled only with what the head-end
//           answered) · MR-25 (a multi-register meter is never filled from one
//           head-end figure) · hard-won law 2 (mounted under the real
//           `/:tenant/reads` route, opened by its real button)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient, ApiResponse } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { QuickReadButton, QuickReadModal } from "./QuickReadModal";
import type { QuickReadContext } from "./QuickReadModal";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function ok<T>(data: T): ApiResponse<T> {
  return { ok: true, status: 200, data } as unknown as ApiResponse<T>;
}

function ctx(channels: string[]): QuickReadContext {
  return {
    meter: { id: "a-5002", asset_no: "M-5002", unit: "kWh", multiplier: "1", service: "electric" },
    read_at: "2026-10-17",
    registers: {
      simple: channels.length === 1,
      channels,
      channel_count: channels.length,
      default_channel: channels.length === 1 ? channels[0] : null,
      absent_reason: null,
      hand_off_to: null,
    },
    cycle: {
      cycle: { id: "c-1", code: "CY-001", name: "Cycle 1" },
      cycle_absent: null,
      route: { id: "r-1", code: "RT-01" },
      period_month: "2026-10-01",
      read_window: null,
      in_window: true,
    },
    pipeline: {},
    rule_refs: [],
  };
}

interface Log {
  fetches: unknown[];
  staged: { rows: { channel: string; reading: string; read_date: string }[] }[];
}

function client(channels: string[], fetchAnswer: unknown, log: Log): ApiClient {
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      if (path === "/reads/quick-context") return ok(ctx(channels) as T);
      return ok({ results: [], count: 0 } as T);
    },
    post: async <T,>(path: string, body?: unknown): Promise<ApiResponse<T>> => {
      if (path === "/integrations/meter-reading/fetch") {
        log.fetches.push(body);
        return ok(fetchAnswer as T);
      }
      if (path === "/read-batches") {
        log.staged.push(body as Log["staged"][number]);
        return ok({ id: "b-1" } as T);
      }
      if (path === "/read-batches/b-1/validate") return ok({ id: "b-1" } as T);
      if (path === "/read-batches/b-1/post") {
        return ok({ posted_reads: 1, batch_no: "RB-1", counts: { warnings: 0 } } as T);
      }
      throw new Error(`unstubbed POST ${path}`);
    },
  } as unknown as ApiClient;
}

function Host(props: { api: ApiClient }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <QuickReadButton onOpen={() => setOpen(true)} t={t} />
      {open && (
        <QuickReadModal
          client={props.api}
          t={t}
          dateFormat="MM/DD/YYYY"
          timeZone="UTC"
          onClose={() => setOpen(false)}
          onPosted={() => setOpen(false)}
        />
      )}
    </>
  );
}

async function openAndLookUp(api: ApiClient) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/reads"]}>
          <Routes>
            <Route path="/:tenant/reads" element={<Host api={api} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: t("metering.quickRead.open") }));
  await user.type(screen.getByLabelText(/meter number/i), "M-5002");
  await user.tab();
  await waitFor(() => expect(screen.getByTestId("quick-read-meter")).toBeInTheDocument());
  return user;
}

const FETCHED = {
  result: "fetched",
  reading: { meter_no: "M-5002", value: "1300", unit: "kWh", read_on: "2026-10-15" },
  message_key: null,
};

describe("DEF-MET-10183 — Add reading has Fetch", () => {
  it("Fetch fills the reading AND its date, and the batch posts the head-end's date", async () => {
    const log: Log = { fetches: [], staged: [] };
    const user = await openAndLookUp(client(["total"], FETCHED, log));
    await user.click(screen.getByRole("button", { name: "Fetch reading for M-5002" }));
    const box = screen.getByLabelText(t("metering.quickRead.valueLabel", { unit: "kWh" }), { exact: false });
    await waitFor(() => expect(box).toHaveValue("1300"));
    expect((log.fetches[0] as { meter_no: string }).meter_no).toBe("M-5002");
    expect(screen.getByText(t("metering.readingEntry.dateFromMeter"))).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: t("metering.quickRead.submit") }));
    await waitFor(() => expect(log.staged).toHaveLength(1));
    expect(log.staged[0].rows[0]).toMatchObject({ channel: "total", reading: "1300", read_date: "2026-10-15" });
  });

  it("no provider: said honestly and nothing is filled", async () => {
    const log: Log = { fetches: [], staged: [] };
    const user = await openAndLookUp(
      client(["total"], { result: "not_connected", reading: null, message_key: "integrations.meterReading.not_connected" }, log),
    );
    await user.click(screen.getByRole("button", { name: "Fetch reading for M-5002" }));
    await screen.findByText(t("integrations.meterReading.not_connected"));
    expect(screen.getByLabelText(t("metering.quickRead.valueLabel", { unit: "kWh" }), { exact: false })).toHaveValue("");
  });

  it("a multi-register meter offers no Fetch — one head-end figure is never split across registers", async () => {
    const log: Log = { fetches: [], staged: [] };
    await openAndLookUp(client(["tou_on", "tou_off", "total"], FETCHED, log));
    expect(screen.queryByRole("button", { name: "Fetch reading for M-5002" })).toBeNull();
    // ONE date for the visit, still.
    expect(screen.getAllByLabelText(t("metering.quickRead.dateLabel"), { exact: false })).toHaveLength(1);
  });
});
