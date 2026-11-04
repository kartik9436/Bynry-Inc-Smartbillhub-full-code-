// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  `DEF-SHL-10751` — five dropdowns started EMPTY with no placeholder.
//          A native select over a value no option carries draws its FIRST
//          option, so the box showed a choice it did not hold: picking that
//          shown option fired no change, and the form said "required" (or, on
//          the optional Sub-group, saved none while showing one). The same
//          shape as `DEF-PAY-10731` (Start counter).
// Code:    AccountDocumentsTab.tsx · CostOfServicePage.tsx ·
//          SaveReportAsModal.tsx · work/dispatchModals.tsx
// ───────────────────────────────────────────────────────
// THE ONE ASSERTION, per box: what the box SHOWS is what the form HOLDS —
// `options[selectedIndex].value === select.value`. Every earlier test set the
// value by firing a change and so could not see the gap.
//
// RED PROVED FIRST (2026-10-30): against the tip's four files every case
// below failed — the shown option carried a real value while the box held "".
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import type React from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { CostRegisterResponse } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";
import i18n from "@/i18n";

import { UploadDocumentForm } from "./customers/AccountDocumentsTab";
import { CaptureModal } from "./ledger/CostOfServicePage";
import { SaveReportAsModal } from "./reports/SaveReportAsModal";
import { BulkModal } from "./work/dispatchModals";

afterEach(cleanup);

const t = (key: string): string => i18n.t(key);

function client(get: (path: string) => unknown = () => ({ results: [], count: 0 })): ApiClient {
  return {
    get: vi.fn((path: string) => Promise.resolve({ status: 200, data: get(path) })),
    post: vi.fn(() => Promise.resolve({ status: 200, data: {} })),
    patch: vi.fn(() => Promise.resolve({ status: 200, data: {} })),
    delete: vi.fn(() => Promise.resolve({ status: 200, data: {} })),
  } as unknown as ApiClient;
}

function mount(element: React.ReactElement) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/here"]}>
          <Routes>
            <Route path="/:tenant/here" element={element} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function box(id: string): HTMLSelectElement {
  const found = document.getElementById(id);
  expect(found, `#${id}`).not.toBeNull();
  return found as HTMLSelectElement;
}

/** The box shows the option it holds, and that option is the placeholder. */
function showsWhatItHolds(id: string, placeholder: string): void {
  const select = box(id);
  expect(select.value).toBe("");
  const shown = select.options[select.selectedIndex];
  expect(shown.value).toBe(select.value);
  expect(shown.textContent).toBe(placeholder);
  // …and at least one real choice follows it.
  expect(select.options.length).toBeGreaterThan(1);
}

describe("DEF-SHL-10751 · a dropdown that starts empty shows a placeholder", () => {
  it("account Documents — Type", () => {
    mount(
      <UploadDocumentForm accountId="acc-1" client={client()} onClose={() => undefined} onFiled={() => undefined} />,
    );
    showsWhatItHolds("document-type", t("customFields.chooseOne"));
  });

  it("Cost of service — Service and Ledger account", async () => {
    const register = {
      rows: [],
      categories: ["water"],
      refused_categories: [],
      pending_finance_re_sign_cost: [],
    } as unknown as CostRegisterResponse;
    mount(
      <CaptureModal
        register={register}
        currency="USD"
        client={client(() => ({
          rows: [{ account_id: "gl-5110", code: "5110", name: "Purchased water", type: "expense" }],
        }))}
        t={t}
        onClose={() => undefined}
        onCaptured={() => undefined}
      />,
    );
    showsWhatItHolds("service", t("finance.taxes.form.basisPlaceholder"));
    await waitFor(() => expect(box("ledger_account_id").options.length).toBeGreaterThan(1));
    showsWhatItHolds("ledger_account_id", t("finance.je.field.accountPlaceholder"));
  });

  it("Save report as — Group and Sub-group", () => {
    mount(
      <SaveReportAsModal
        initialName="Overdue 60+"
        initialGroup=""
        initialSubGroup={null}
        groups={[
          { code: "receivables", name: "Receivables", sub_groups: [] },
          { code: "billing", name: "Billing", sub_groups: [] },
        ]}
        onSave={async () => ({}) as never}
        onSaved={() => undefined}
        onClose={() => undefined}
      />,
    );
    showsWhatItHolds("group", t("reports.input.choose"));
  });

  it("Save report as — an optional Sub-group shows none when none is held", () => {
    mount(
      <SaveReportAsModal
        initialName="Overdue 60+"
        initialGroup="receivables"
        initialSubGroup={null}
        groups={[
          {
            code: "receivables",
            name: "Receivables",
            sub_groups: [{ code: "receivables_arrears", name: "Arrears" }],
          },
        ]}
        onSave={async () => ({}) as never}
        onSaved={() => undefined}
        onClose={() => undefined}
      />,
    );
    showsWhatItHolds("sub_group", t("reports.input.choose"));
  });

  it("Work orders bulk — Change priority", () => {
    mount(
      <BulkModal
        act="priority"
        ids={["wo-0040"]}
        held={0}
        priorities={[
          { value: "p-high", label: "High" },
          { value: "p-low", label: "Low" },
        ]}
        client={client()}
        onSubmit={async () => ({ ok: true }) as never}
        onClose={() => undefined}
      />,
    );
    showsWhatItHolds("priority", t("customers.build.raise.pick"));
  });
});
