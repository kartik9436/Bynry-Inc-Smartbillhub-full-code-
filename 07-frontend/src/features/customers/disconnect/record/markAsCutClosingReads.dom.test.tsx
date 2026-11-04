// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-10166 — Mark as cut takes a closing reading, its read date
//           and Fetch (PO 2026-10-17, decision log *"WHERE A USER ENTERS A
//           METER READING"*, gap 3), through the shared MeterReadingEntry.
// Tests:    MarkAsCutDialog.tsx, mounted from DisconnectRecordPage at its REAL
//           route (`/:tenant/disconnects/:ref`) — hard-won law 2's footnote.
// ───────────────────────────────────────────────────────
// WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2): a reading drawn and
// never posted (the POSTED body is asserted field by field); a cut that posts
// with an empty box (the required case asserts NO post); a No access tick that
// still sends a row (the body is asserted without it); a read date that does
// not follow the cut date (asserted after the cut date moves).
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Mock } from "vitest";

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { DISCONNECT_RECORD_ROUTE, DisconnectRecordPage, disconnectRecordPath } from "./DisconnectRecordPage";
import { disconnectRecordKey } from "./disconnectRecordEndpoints";
import type { DisconnectRecordDetail } from "./disconnectRecordEndpoints";

afterEach(cleanup);

const ACCOUNT_ID = "01a0bf3d-13c5-7cfa-96a1-486d6b84f070";
const CASE_NO = "DSC-26-0003";

const ABSENT = (code: string, detail: string) => ({ code, detail });

function detail(over: Partial<DisconnectRecordDetail> = {}): DisconnectRecordDetail {
  return {
    case_no: { value: "DSC-26-0003", unavailable: null },
    customer_name: { value: "Bramble Bakery", unavailable: null },
    address: { value: "142 Bakers Row · Suite 1 · Silver Creek, TX 78611", unavailable: null },
    customer_class: { value: "Commercial", unavailable: null },
    state: { value: "scheduled", unavailable: null },
    tier: { value: "tier_3_48_hour", unavailable: null },
    cut_date: { value: "2026-05-14", unavailable: null },
    the_case: {
      account_no: { value: "A-11812", unavailable: null },
      owed: { stored: "2410.0000", display: "2410.00", currency: "USD", unavailable: null },
      oldest_debt: { value: null, unavailable: ABSENT("oldest_debt_age_has_no_source", "none") },
      tier: { value: "tier_3_48_hour", unavailable: null },
      cut_date: { value: "2026-05-14", unavailable: null },
      opened_on: { value: "2026-04-14", unavailable: null },
      raised_by: { value: null, unavailable: ABSENT("case_opener_not_recorded", "none") },
    },
    notices: {
      rows: [],
      state_column_unavailable: ABSENT("notice_delivery_state_is_null_by_rule", "by rule"),
      channel_column_empty: ABSENT("service_channel_is_the_proof_channel", "not attested"),
      delivery: ABSENT("delivery_adapter_absent", "no adapter"),
    },
    protections: {
      as_of: "2026-05-14",
      checks: [
        // p143's drawn order, which is NOT `disconnects.PROTECTIONS`' —
        // the server re-orders it (`disconnect_record.DRAWN_ORDER`) and the
        // fixture carries what ships rather than what the writer declares.
        { check: "medical_certificate", outcome: "pass", reason: "none in force" },
        { check: "weather_moratorium", outcome: "pass", reason: "none in force" },
        { check: "payment_plan", outcome: "pass", reason: "none in force" },
        { check: "dispute", outcome: "unavailable", reason: "nothing stores a disputed amount" },
      ],
      all_clear: true,
    },
    what_a_cut_would_do: {
      services_affected: { value: ["electric", "water"], unavailable: null },
      reconnection_fee: {
        charge_code_configured: false,
        stored: null,
        display: null,
        currency: "USD",
        unavailable: ABSENT("reconnect_charge_code_not_seeded", "no seed creates that code"),
      },
      account_status_becomes: ABSENT("disconnected_status_assigned_at_the_cut", "BR-CUS-107"),
      to_clear_before_reconnection: {
        stored: null,
        display: null,
        currency: "USD",
        unavailable: ABSENT("reconnect_charge_code_not_seeded", "no seed"),
      },
      base_charges: ABSENT("base_charges_stop_at_the_cut", "BR-CUS-103"),
      not_a_close_out: ABSENT("a_cut_is_not_a_close_out", "the account stays open"),
    } as DisconnectRecordDetail["what_a_cut_would_do"],
    actions: {
      available: ["hold", "open_account", "mark_as_cut"],
      account_id: ACCOUNT_ID,
      hold: {
        kinds: ["medical_certificate", "weather_moratorium", "payment_plan"],
        review_date: {
          medical_certificate: "required",
          payment_plan: "refused",
          weather_moratorium: "required",
        },
        dispute_unrecordable: ABSENT("dispute_is_not_a_protection", "nothing stores an amount"),
        effects: [
          { when: "now", code: "ladder_stops" },
          { when: "not_now", code: "cut_date_stays" },
          { when: "not_now", code: "debt_stays_and_ages" },
        ],
        promises_not_kept: ABSENT("hold_clears_no_date_and_moves_no_state", "measured"),
      },
      mark_as_cut: { ready: true, refusal: null, blockers: [] },
    },
    ...over,
  };
}

function withMeters(): DisconnectRecordDetail {
  const base = detail();
  return {
    ...base,
    actions: {
      ...base.actions,
      closing_reads: {
        meters: [
          {
            asset_no: "E-7001",
            service: "electric",
            kind: "meter",
            unit: "kWh",
            last_read: { value: "43000.000000", read_at: "2026-05-01" },
          },
          { asset_no: "W-7002", service: "water", kind: "meter", unit: "kgal", last_read: null },
        ],
      },
    },
  };
}

function client(record: DisconnectRecordDetail, fetchAnswer?: unknown): ApiClient & { post: Mock; get: Mock } {
  return {
    post: vi.fn(async (path: string) =>
      path === "/integrations/meter-reading/fetch"
        ? { status: 200, data: fetchAnswer }
        : { status: 201, data: { account_status_written: "disconnected" } },
    ),
    get: vi.fn(async () => ({ status: 200, data: record })),
  } as unknown as ApiClient & { post: Mock; get: Mock };
}

function mount(record: DisconnectRecordDetail, api: ApiClient) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  qc.setQueryData(disconnectRecordKey(CASE_NO), record);
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/brazosbend${disconnectRecordPath(CASE_NO)}`]}>
          <Routes>
            <Route
              path={`/:tenant${DISCONNECT_RECORD_ROUTE}`}
              element={<DisconnectRecordPage client={api} timeZone="UTC" dateFormat="MM/DD/YYYY" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function openDialog(): Promise<HTMLElement> {
  await userEvent.click(await screen.findByRole("button", { name: "Mark as cut" }));
  return screen.findByRole("dialog");
}

const cutPosts = (api: { post: Mock }) =>
  api.post.mock.calls.filter(([path]) => path === `/accounts/${ACCOUNT_ID}/disconnect-case/cut`);

describe("DEF-CUS-10166 — closing readings on Mark as cut", () => {
  it("draws one reading, read date and Fetch per meter; no Estimate", async () => {
    const api = client(withMeters());
    mount(withMeters(), api);
    const dialog = await openDialog();
    const rows = dialog.querySelectorAll("[data-closing-read]");
    expect([...rows].map((row) => row.getAttribute("data-closing-read"))).toEqual(["E-7001", "W-7002"]);
    expect(within(dialog).getByRole("button", { name: "Fetch reading for E-7001" })).toBeInTheDocument();
    // The read date opens on the cut date.
    expect(within(dialog).getByLabelText(/^Read date for E-7001/)).toHaveValue("05/14/2026");
    expect(within(dialog).getByText("Last 43,000 kWh · 05/01/2026")).toBeInTheDocument();
    expect(within(dialog).queryByLabelText(/Estimate/)).toBeNull();
  });

  it("posts the closing readings with their dates beside the cut date", async () => {
    const api = client(withMeters());
    mount(withMeters(), api);
    const dialog = await openDialog();
    await userEvent.type(within(dialog).getByLabelText(/^Reading for E-7001/), "43566");
    const date = within(dialog).getByLabelText(/^Read date for E-7001/);
    await userEvent.clear(date);
    await userEvent.type(date, "05/13/2026");
    await userEvent.type(within(dialog).getByLabelText(/^Reading for W-7002/), "2531");
    await userEvent.click(within(dialog).getByRole("button", { name: /Mark as cut/ }));
    await waitFor(() => expect(cutPosts(api)).toHaveLength(1));
    expect(cutPosts(api)[0][1]).toEqual({
      cut_on: "2026-05-14",
      final_reads: [
        { meter_no: "E-7001", value: "43566", read_at: "2026-05-13" },
        { meter_no: "W-7002", value: "2531", read_at: "2026-05-14" },
      ],
    });
    // DEF-CUS-10168 — the dialog closes once the cut has committed.
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  }, 20000);

  it("a reading is required unless No access is ticked, and a ticked meter sends no row", async () => {
    const api = client(withMeters());
    mount(withMeters(), api);
    const dialog = await openDialog();
    await userEvent.type(within(dialog).getByLabelText(/^Reading for E-7001/), "43566");
    await userEvent.click(within(dialog).getByRole("button", { name: /Mark as cut/ }));
    expect(await within(dialog).findByText("Enter the reading.")).toBeInTheDocument();
    expect(cutPosts(api)).toHaveLength(0);
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "No access to W-7002" }));
    await userEvent.click(within(dialog).getByRole("button", { name: /Mark as cut/ }));
    await waitFor(() => expect(cutPosts(api)).toHaveLength(1));
    expect(cutPosts(api)[0][1]).toEqual({
      cut_on: "2026-05-14",
      final_reads: [{ meter_no: "E-7001", value: "43566", read_at: "2026-05-14" }],
    });
  });

  it("a date before the meter's last reading holds the cut and says why", async () => {
    const api = client(withMeters());
    mount(withMeters(), api);
    const dialog = await openDialog();
    await userEvent.type(within(dialog).getByLabelText(/^Reading for E-7001/), "43566");
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "No access to W-7002" }));
    const date = within(dialog).getByLabelText(/^Read date for E-7001/);
    await userEvent.clear(date);
    await userEvent.type(date, "04/30/2026");
    await userEvent.click(within(dialog).getByRole("button", { name: /Mark as cut/ }));
    expect(await within(dialog).findByText("Earlier than the last reading.")).toBeInTheDocument();
    expect(cutPosts(api)).toHaveLength(0);
  });

  it("Fetch asks for the reading as of the cut date and fills the row with the meter's date", async () => {
    const api = client(withMeters(), {
      result: "fetched",
      reading: { meter_no: "E-7001", value: "43590", unit: "kWh", read_on: "2026-05-12" },
      message_key: null,
    });
    mount(withMeters(), api);
    const dialog = await openDialog();
    await userEvent.click(within(dialog).getByRole("button", { name: "Fetch reading for E-7001" }));
    await waitFor(() => expect(within(dialog).getByLabelText(/^Reading for E-7001/)).toHaveValue("43590"));
    expect(api.post).toHaveBeenCalledWith("/integrations/meter-reading/fetch", {
      meter_no: "E-7001",
      as_of: "2026-05-14",
    });
    expect(within(dialog).getByLabelText(/^Read date for E-7001/)).toHaveValue("05/12/2026");
  });

  it("an honest no-reading answer leaves the box empty and says so", async () => {
    const api = client(withMeters(), {
      result: "not_connected",
      reading: null,
      message_key: "integrations.meterReading.not_connected",
    });
    mount(withMeters(), api);
    const dialog = await openDialog();
    await userEvent.click(within(dialog).getByRole("button", { name: "Fetch reading for E-7001" }));
    expect(await within(dialog).findByText("Provider is not connected.")).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/^Reading for E-7001/)).toHaveValue("");
  });

  it("a case with no meters posts the cut date alone, as before", async () => {
    const api = client(detail());
    mount(detail(), api);
    const dialog = await openDialog();
    expect(dialog.querySelector('[data-testid="disconnect-cut-reads"]')).toBeNull();
    await userEvent.click(within(dialog).getByRole("button", { name: /Mark as cut/ }));
    await waitFor(() => expect(cutPosts(api)).toHaveLength(1));
    expect(cutPosts(api)[0][1]).toEqual({ cut_on: "2026-05-14" });
  });
});
