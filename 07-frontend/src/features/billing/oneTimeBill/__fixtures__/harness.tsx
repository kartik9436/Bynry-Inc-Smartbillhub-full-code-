/**
 * A capture harness for the one-time bill page: the real page, the real
 * stylesheets, and an API answered from `oneTimeBillFixtures.ts` — so every
 * drawn state can be screenshotted without a booted backend (which is being
 * built to the same contract in parallel). Not part of the product bundle:
 * only `otb-harness.html` loads it, under `npm run dev`.
 *
 * Query: `?kind=<kind>` · `&dup=1` (already billed) · `&reads=1` (readings on
 * file, so steps 3 and 4 are reachable) · `&rollover=1` (the meter rolled
 * over inside the period — DEF-BIL-9077 — held until Accept is pressed).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ReactDOM from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import "@/i18n";
import "@/styles/global.css";
import "@/styles/tailwind.css";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import type { OneTimeBillKind } from "@/api/billingOpsEndpoints";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { OneTimeBillPage } from "../OneTimeBillPage";

import { accountRow, previewFor } from "./oneTimeBillFixtures";

const params = new URLSearchParams(window.location.search);
const dup = params.get("dup") === "1";
const reads = params.get("reads") === "1";
const rollover = params.get("rollover") === "1";
/** Set once a reading batch posts: the saved move-in read is then ON FILE, as
 *  the server would say on the next preview. */
let posted = false;

function ok(data: unknown) {
  return new Promise((resolve) =>
    setTimeout(() => resolve({ status: 200, data, etag: null, notModified: false }), 30),
  );
}

function answer(path: string, body: unknown): Promise<unknown> {
  if (path === "/me/permissions") return ok({ permissions: [{ code: "reads_billing_runs", access: "Full" }] });
  if (path === "/accounts") {
    return ok({
      count: 4,
      rollup: {},
      results: [
        accountRow(),
        accountRow({ id: "a2", name: "Luis Alvarez", account_no: "AC-2026-00117", premise: "22 Birch Ct", unit_label: null }),
        accountRow({ id: "a3", name: "Alvarez Hardware LLC", account_no: "AC-2026-00388", premise: "900 Main St", unit_label: "Suite 2" }),
        accountRow({ id: "a4", name: "Maria Alvarez", account_no: "AC-2025-01904", premise: "61 Oak Ave", unit_label: null, status_name: "Closed", status_behavior_class: "terminal" }),
      ],
    });
  }
  if (path === "/payments/reason-codes") {
    return ok({ reasons: [{ code: "MISSED", name: "Missed billing cycle" }, { code: "FAULT", name: "Meter fault found" }, { code: "THEFT", name: "Theft of service" }], count: 3 });
  }
  if (path === "/charges") {
    return ok({ count: 2, results: [{ code: "RECON", name: "Reconnection fee", amount: "75.0000" }, { code: "TAMPER", name: "Tamper charge", amount: "250.0000" }] });
  }
  if (path === "/billing/one-time/preview") {
    const b = body as { kind: OneTimeBillKind; accepted_rollovers?: string[] };
    if (rollover && !(b.accepted_rollovers ?? []).includes("electric")) {
      return new Promise((_resolve, reject) =>
        setTimeout(
          () =>
            reject(
              new ApiError(422, {
                code: "BIZ-COMPLETENESS",
                message_key: "billing.oneTime.err.rolloverHeld",
                params: {
                  reason: "possible_rollover",
                  service_code: "electric",
                  service: "Electric",
                  meter: "E-55120",
                  from: "99800.000000",
                  to: "240.000000",
                  closing: "700.000000",
                  suggested_quantity: "900.000000",
                  unit: "kWh",
                },
                field_errors: [],
              }),
            ),
          30,
        ),
      );
    }
    const p = previewFor(b.kind, dup ? { duplicate: { invoice_no: "BL-2609-000211", run_id: "r0", invoice_id: "inv-0", ran_by_name: "J. Ortiz", ran_at: "2026-09-18T10:00:00-05:00" } } : {});
    if (posted && p.readings !== null) {
      p.readings.rows = p.readings.rows.map((r) => ({ ...r, previous: { ...r.previous, value: r.previous.value ?? "128.9", on_file: true } }));
    }
    if (reads && p.readings !== null) {
      const onFile: Record<string, [string, string]> = {
        "W-10442": ["488.4", "6.1"],
        "W-10443": ["134.9", "4.3"],
        "E-55120": ["19030", "610"],
      };
      p.readings.rows = p.readings.rows.map((r) => ({
        ...r,
        current: { ...r.current, value: r.current.value ?? onFile[r.label]?.[0] ?? null },
        usage: r.usage ?? onFile[r.label]?.[1] ?? null,
        status: r.status === "waiting" ? "accepted" : r.status,
      }));
    }
    return ok(p);
  }
  if (path === "/billing/one-time") {
    return ok({ run_id: "run-1", invoice_id: "inv-1", invoice_no: "BL-2609-000318", total: previewFor("interim").bill.total, currency: "USD", due_date: "2026-10-21", bill: previewFor("interim").bill, warnings: previewFor("interim").warnings });
  }
  if (path.endsWith("/send")) {
    return ok({ invoice_no: "BL-2609-000318", total: "168.4900", currency: "USD", due_date: "2026-10-21", delivery: "queued", reads: "locked" });
  }
  if (path === "/read-batches") return ok({ id: "b1" });
  if (path === "/read-batches/b1/post") {
    posted = true;
    return ok({ id: "b1", posted_reads: 1 });
  }
  if (path === "/read-batches/b1") return ok({ id: "b1", rows: [] });
  return ok({ id: "b1", count: 0, results: [] });
}

const client = {
  get: (path: string) => answer(path, undefined),
  post: (path: string, body?: unknown) => answer(path, body),
  request: (path: string, options?: { body?: unknown }) => answer(path, options?.body),
} as unknown as ApiClient;

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
const root = document.getElementById("root") as HTMLElement;
ReactDOM.createRoot(root).render(
  <QueryClientProvider client={queryClient}>
    <ToastProvider>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <MemoryRouter initialEntries={[`/demo/billing/one-time${window.location.search}`]}>
          <main className="mx-auto max-w-7xl p-6">
            <Routes>
              <Route path="/:tenant/billing/one-time" element={<OneTimeBillPage client={client} />} />
            </Routes>
          </main>
        </MemoryRouter>
      </TenantRegionalProvider>
    </ToastProvider>
  </QueryClientProvider>,
);
