/**
 * A capture harness for the bulk bill run: the real page, the real
 * stylesheets, and an API answered from `bulkRunFixtures.ts` — so every drawn
 * state can be screenshotted without a booted backend. Not part of the product
 * bundle: only `bulk-run-harness.html` loads it, under `npm run dev`.
 *
 * Query: `?scope=continuous|gap|overlap|warnings|problems` · `&run=<id>` to
 * open the run · `&phase=draft|calculated|authorised|issued` · `&down=1`
 * (Meter Reads not answering) · `&checking=1` (findings still loading).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ReactDOM from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import "@/i18n";
import "@/styles/global.css";
import "@/styles/tailwind.css";

import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { BulkRunPage } from "../BulkRunPage";

import type { ScopeState } from "./bulkRunFixtures";
import { fakeClient } from "./fakeClient";

const params = new URLSearchParams(window.location.search);
const { client } = fakeClient({
  scope: (params.get("scope") ?? "continuous") as ScopeState,
  phase: params.get("phase") ?? "draft",
  moduleDown: params.get("down") === "1",
  checking: params.get("checking") === "1",
  delay: 20,
});
const search = params.get("run") === null ? "" : `?run=${params.get("run")}`;

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
const root = document.getElementById("root") as HTMLElement;
ReactDOM.createRoot(root).render(
  <QueryClientProvider client={queryClient}>
    <ToastProvider>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <MemoryRouter initialEntries={[`/demo/billing/run${search}`]}>
          <main className="mx-auto max-w-7xl p-6">
            <Routes>
              <Route path="/:tenant/billing/run" element={<BulkRunPage client={client} />} />
            </Routes>
          </main>
        </MemoryRouter>
      </TenantRegionalProvider>
    </ToastProvider>
  </QueryClientProvider>,
);
