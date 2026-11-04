// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-10183 — Billing → One-time bill step 2 had no Fetch. PO
//           ruling 2026-10-17 (decision log "WHERE A USER ENTERS A METER
//           READING", gap 5); the same day: "use same code components" — each
//           meter's new reading, its date and Fetch are `MeterReadingEntry`.
// Rules:    hard-won law 1 (only what the head-end answered fills the box) ·
//           BR-TEN-043 (a fixed move-out date is not moved by a fetch) ·
//           hard-won law 2 (mounted under the real `/:tenant/billing/one-time`)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import i18n from "i18next";
import { useState } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient, ApiResponse } from "@/api/client";
import type { OneTimeBillPreview, OneTimeBillReadingRow } from "@/api/billingOpsEndpoints";

import { ReadingsPanel } from "./ServicesStep";
import { emptyForm } from "./oneTimeBillModel";
import type { OneTimeBillForm } from "./oneTimeBillModel";
import type { OtbFormat } from "./oneTimeBillShared";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;
const fmt: OtbFormat = { t, currency: "USD", timeZone: "UTC", dateFormat: "MM/DD/YYYY" };

function row(over: Partial<OneTimeBillReadingRow["current"]> = {}): OneTimeBillReadingRow {
  return {
    asset_id: "m-460",
    label: "W-10460",
    unit: "kgal",
    previous: { value: "312.4", read_at: "2026-08-31", on_file: true },
    current: { value: null, read_at: "2026-09-30", fixed_date: false, ...over },
    usage: null,
    status: "waiting",
    refusal_key: null,
    period_index: null,
  };
}

function preview(r: OneTimeBillReadingRow): OneTimeBillPreview {
  return {
    account: { moved_in_on: null },
    services: [{ service: "water", assets: [{ asset_id: "m-460", label: "W-10460" }], status: "billed" }],
    readings: { needed: "every_meter", rows: [r] },
  } as unknown as OneTimeBillPreview;
}

function client(answer: unknown, asked: unknown[]): ApiClient {
  return {
    post: async <T,>(path: string, body?: unknown): Promise<ApiResponse<T>> => {
      if (path !== "/integrations/meter-reading/fetch") throw new Error(`unstubbed POST ${path}`);
      asked.push(body);
      return { status: 200, etag: null, notModified: false, data: answer } as unknown as ApiResponse<T>;
    },
  } as unknown as ApiClient;
}

let latest: OneTimeBillForm | null = null;

function Host(props: { kind: "interim" | "final"; r: OneTimeBillReadingRow; api: ApiClient }) {
  const [form, setForm] = useState<OneTimeBillForm>(emptyForm(props.kind, "2026-09-30"));
  latest = form;
  return (
    <ReadingsPanel
      preview={preview(props.r)}
      form={form}
      onChange={(key, patch) =>
        setForm((was) => ({
          ...was,
          readings: { ...was.readings, [key]: { ...(was.readings[key] ?? { value: "", readAt: "" }), ...patch } },
        }))
      }
      readsHref="/brazosbend/reads"
      client={props.api}
      t={t}
      fmt={fmt}
    />
  );
}

function mount(kind: "interim" | "final", r: OneTimeBillReadingRow, api: ApiClient) {
  render(
    <MemoryRouter initialEntries={["/brazosbend/billing/one-time"]}>
      <Routes>
        <Route path="/:tenant/billing/one-time" element={<Host kind={kind} r={r} api={api} />} />
      </Routes>
    </MemoryRouter>,
  );
}

const FETCHED = {
  result: "fetched",
  reading: { meter_no: "W-10460", value: "318.9", unit: "kgal", read_on: "2026-09-28" },
  message_key: null,
};

describe("DEF-MET-10183 — one-time bill step 2 has Fetch per meter", () => {
  it("asks as of the bill's read date and fills the new reading AND its date", async () => {
    const asked: unknown[] = [];
    mount("interim", row(), client(FETCHED, asked));
    await userEvent.click(screen.getByRole("button", { name: "Fetch reading for W-10460" }));
    await waitFor(() => expect(screen.getByLabelText(/New reading for W-10460/)).toHaveValue("318.9"));
    expect(asked).toEqual([{ meter_no: "W-10460", as_of: "2026-09-30" }]);
    const entry = Object.values(latest?.readings ?? {})[0];
    expect(entry).toEqual({ value: "318.9", readAt: "2026-09-28" });
  });

  it("a move-out's fixed date is not moved by the fetch", async () => {
    const asked: unknown[] = [];
    mount("final", row({ fixed_date: true }), client(FETCHED, asked));
    await userEvent.click(screen.getByRole("button", { name: "Fetch reading for W-10460" }));
    await waitFor(() => expect(Object.values(latest?.readings ?? {})[0]).toEqual({ value: "318.9", readAt: "2026-09-30" }));
    expect(document.getElementById("read-date-m-460|current|")).toBeNull();
  });

  it("no provider: says so, fills nothing", async () => {
    const asked: unknown[] = [];
    mount(
      "interim",
      row(),
      client({ result: "not_connected", reading: null, message_key: "integrations.meterReading.not_connected" }, asked),
    );
    await userEvent.click(screen.getByRole("button", { name: "Fetch reading for W-10460" }));
    await screen.findByText(t("integrations.meterReading.not_connected"));
    expect(screen.getByLabelText(/New reading for W-10460/)).toHaveValue("");
  });
});
