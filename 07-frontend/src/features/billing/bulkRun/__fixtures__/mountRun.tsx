/**
 * Mount the bulk run page under its REAL route pattern (`/:tenant/billing/run`)
 * with the fake client — shared by the component and every-link tests.
 * TEST ONLY.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import { BulkRunPage } from "../BulkRunPage";

import { fakeClient } from "./fakeClient";
import type { FakeOptions } from "./fakeClient";

export const TENANT = "brazosbend";

export const where = { location: "" };

function Where() {
  const location = useLocation();
  where.location = `${location.pathname}${location.search}`;
  return null;
}

export function mountRun(options: FakeOptions = {}, search = "") {
  const fake = fakeClient(options);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
          <MemoryRouter initialEntries={[`/${TENANT}/billing/run${search}`]}>
            <Routes>
              <Route
                path="/:tenant/billing/run"
                element={
                  <>
                    <BulkRunPage client={fake.client as ApiClient} />
                    <Where />
                  </>
                }
              />
            </Routes>
          </MemoryRouter>
        </TenantRegionalProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return fake;
}
