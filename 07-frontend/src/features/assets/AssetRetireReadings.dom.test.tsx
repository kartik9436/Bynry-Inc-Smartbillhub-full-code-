// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-AST-10182 — Assets → Retire with a replacement meter. PO ruling
//           2026-10-17 (decision log "WHERE A USER ENTERS A METER READING",
//           gap 2): the NEW meter's opening reading + read date, and Fetch
//           for the old meter's final reading AND the new meter's opening one.
//           PO, same day: "use same code components" — both are the shared
//           `MeterReadingEntry`.
// Rules:    hard rule 3 (each reading in its own meter's unit) · hard-won
//           law 2 (mounted under the REAL route pattern, so `useParams` and
//           the tenant path are what the router gives)
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { AssetRetireWizard } from "./AssetRetireWizard";
import { asset, detail } from "./assetTestFixtures";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const TENANT = "brazosbend";

const OLD = detail({ id: "a-4022", asset_no: "M-4022", unit: "kgal" });
const SPARE = asset({
  id: "a-9101",
  asset_no: "M-9101",
  status: "inventory",
  status_name: "Inventory/Spare",
  behavior_class: "available",
  unit: "kgal",
  tab: "meters",
});

interface Call {
  method: string;
  path: string;
  body: Record<string, unknown> | null;
}

function harness(fetchAnswers: Record<string, unknown>) {
  const calls: Call[] = [];
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: async (input, init) => {
      const url = new URL(String(input), "http://x");
      const path = url.pathname.replace(`/api/${TENANT}`, "");
      const method = (init?.method ?? "GET").toUpperCase();
      const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null;
      calls.push({ method, path, body });
      if (path === "/integrations/meter-reading/fetch") {
        const meter = String(body?.meter_no);
        return new Response(JSON.stringify(fetchAnswers[meter]), { status: 200 });
      }
      if (method === "GET" && path === `/assets/${OLD.id}`) {
        return new Response(JSON.stringify(OLD), { status: 200 });
      }
      if (method === "POST" && path.endsWith("/retire")) {
        return new Response(JSON.stringify(asset({ status: "retired" })), { status: 200 });
      }
      return new Response(JSON.stringify({ count: 0, next: null, previous: null, results: [] }), {
        status: 200,
      });
    },
  });
  return { client, calls };
}

function mount(fetchAnswers: Record<string, unknown>) {
  const { client, calls } = harness(fetchAnswers);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(["assets", "detail", OLD.id], OLD);
  queryClient.setQueryData(["assets", "retire-replacement-picker", "meters"], {
    count: 1,
    next: null,
    previous: null,
    results: [SPARE],
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/assets/${OLD.id}/retire?step=1`]}>
          <Routes>
            <Route
              path="/:tenant/assets/:assetId/retire"
              element={
                <AssetRetireWizard client={client} today="2026-08-16" timeZone="UTC" dateFormat="MM/DD/YYYY" />
              }
            />
            <Route path="/:tenant/assets" element={<p>registry</p>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return calls;
}

const FETCHED_OLD = {
  result: "fetched",
  reading: { meter_no: "M-4022", value: "1500.25", unit: "kgal", read_on: "2026-08-10" },
  message_key: null,
};
const NO_PROVIDER = {
  result: "not_connected",
  reading: null,
  message_key: "integrations.meterReading.not_connected",
};

async function continueStep() {
  await userEvent.click(screen.getByRole("button", { name: new RegExp(t("wizard.continue")) }));
}

describe("DEF-AST-10182 — retire with a replacement takes both readings", () => {
  it("Fetch fills the OLD meter's final reading and its own date, asked as of the retire date", async () => {
    const calls = mount({ "M-4022": FETCHED_OLD });
    await screen.findByLabelText(t("assets.retire.finalRead", { unit: "kgal" }));
    await userEvent.click(screen.getByRole("button", { name: "Fetch reading for M-4022" }));
    await waitFor(() =>
      expect(screen.getByLabelText(t("assets.retire.finalRead", { unit: "kgal" }))).toHaveValue("1500.25"),
    );
    const fetchCall = calls.find((c) => c.path === "/integrations/meter-reading/fetch");
    expect(fetchCall?.body).toEqual({ meter_no: "M-4022", as_of: "2026-08-16" });
    expect(screen.getByText(t("metering.readingEntry.dateFromMeter"))).toBeInTheDocument();
  }, 30000);

  it("the NEW meter's opening reading + date are taken, Fetch says honestly there is no provider, and the retire sends both", async () => {
    const calls = mount({ "M-4022": FETCHED_OLD, "M-9101": NO_PROVIDER });
    await screen.findByLabelText(t("assets.retire.finalRead", { unit: "kgal" }));
    await userEvent.selectOptions(screen.getByLabelText(new RegExp(t("assets.retire.reason"))), "replaced");
    await userEvent.click(screen.getByRole("button", { name: "Fetch reading for M-4022" }));
    await waitFor(() =>
      expect(screen.getByLabelText(t("assets.retire.finalRead", { unit: "kgal" }))).toHaveValue("1500.25"),
    );
    await continueStep();

    // Step 2: pick the spare. Before a replacement is named there is no opening box.
    expect(screen.queryByLabelText(t("assets.add.openingRead"))).toBeNull();
    await userEvent.type(screen.getByRole("combobox", { name: new RegExp(t("assets.retire.replacedBy")) }), "M");
    await userEvent.click(await screen.findByRole("option", { name: /M-9101/ }));
    const opening = await screen.findByLabelText(t("assets.add.openingRead"));

    // Fetch on the new meter: no provider → said in words, nothing filled.
    await userEvent.click(screen.getByRole("button", { name: "Fetch reading for M-9101" }));
    const said = await screen.findByText(t("integrations.meterReading.not_connected"));
    expect(said).toBeInTheDocument();
    expect(opening).toHaveValue("");

    // Typed instead. The date opens on the retire date; a future date is refused.
    await userEvent.type(opening, "12");
    const date = document.getElementById("replacement_opening_read_date") as HTMLInputElement;
    expect(date).not.toBeNull();
    fireEvent.change(date, { target: { value: "08/20/2026" } });
    fireEvent.blur(date);
    await screen.findByText(t("metering.readingEntry.error.dateFuture"));
    await continueStep();
    // Still on step 2 — the refusal held the wizard.
    expect(screen.getByLabelText(t("assets.add.openingRead"))).toBeInTheDocument();
    fireEvent.change(date, { target: { value: "08/15/2026" } });
    fireEvent.blur(date);
    await waitFor(() => expect(screen.queryByText(t("metering.readingEntry.error.dateFuture"))).toBeNull());
    await continueStep();

    // Step 3 and commit.
    const commit = await screen.findByRole("button", { name: new RegExp("Retire M-4022") });
    await userEvent.click(commit);
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/retire"))).toBe(true));
    const sent = calls.find((c) => c.method === "POST" && c.path.endsWith("/retire"))?.body;
    expect(sent).toMatchObject({
      reason: "replaced",
      replaced_by: "M-9101",
      final_read_value: "1500.25",
      final_read_date: "2026-08-10",
      replacement_opening_read: "12",
      replacement_opening_read_date: "2026-08-15",
    });
    // No estimate on either meter (PO ruling).
    expect(within(document.body).queryByLabelText(t("metering.readingEntry.estimate"))).toBeNull();
  }, 30000);
});
