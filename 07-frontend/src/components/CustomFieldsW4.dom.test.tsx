// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 wave W4 — customers, work orders, readings, routes and
//          areas carry the utility's own fields. PO 2026-10-02, Part 2 rows 2
//          and 10–13.
// Rules:   BR-TEN-052 (required only where typed in; an edit sends only what
//          changed) · B14 rule 43 (the ONE `CustomFields` component) ·
//          Part 2 row 11 (a reading's answers never reach the bill)
// ───────────────────────────────────────────────────────
// The worked examples: *Seal number = S-2207* on a 1,284 kWh reading;
// *Preferred language = Spanish → French* on a customer.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient } from "@/api/client";
import type { CustomFieldRegistryEntry } from "@/api/endpoints";
import { CustomerEditDialog } from "@/features/customers/CustomerEditDialog";
import type { CustomerRow } from "@/features/customers/customerEndpoints";
import { createAccountPayload, emptyCustomerForm, emptyPreferencesForm } from "@/features/customers/NewAccountWizard";
import { quickReadBatchRequest } from "@/features/metering/QuickReadModal";
import i18n from "@/i18n";

import { missingRequiredLabels } from "./CustomFields";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

function field(over: Partial<CustomFieldRegistryEntry>): CustomFieldRegistryEntry {
  return {
    id: "cf-1",
    key: "seal_number",
    label: "Seal number",
    help_text: "",
    data_type: "text",
    options: [],
    is_required: false,
    display_order: 1,
    placement: {},
    ...over,
  };
}

describe("CR-161 W4 · a wizard names a required field before Continue", () => {
  it("names each required field left blank, and nothing else", () => {
    const fields = [
      field({ key: "seal_number", label: "Seal number", is_required: true }),
      field({ key: "gate_key", label: "Gate key", is_required: false }),
      field({ key: "tags", label: "Tags", data_type: "multi_select", is_required: true }),
      field({ key: "locked", label: "Locked", data_type: "boolean", is_required: true }),
    ];
    expect(missingRequiredLabels(fields, {})).toEqual(["Seal number", "Tags", "Locked"]);
    expect(missingRequiredLabels(fields, { seal_number: "  ", tags: [] })).toEqual([
      "Seal number",
      "Tags",
      "Locked",
    ]);
    // A Yes/No answered "No" IS an answer — the server agrees.
    expect(
      missingRequiredLabels(fields, { seal_number: "S-2207", tags: ["A"], locked: false }),
    ).toEqual([]);
  });
});

describe("CR-161 W4 · Manual reading entry (READ_ENTRY) carries the answers on every register", () => {
  it("one visit, one set of answers, on each register row it stages", () => {
    const request = quickReadBatchRequest({
      meter_no: "M-4021",
      read_date: "2026-07-05",
      notes: "",
      cycleId: null,
      registers: [
        { channel: "total", reading: "1284" },
        { channel: "demand", reading: "7.2" },
      ],
      customData: { seal_number: "S-2207" },
    });
    expect(request.rows.map((row) => row.custom_data)).toEqual([
      { seal_number: "S-2207" },
      { seal_number: "S-2207" },
    ]);
  });

  it("a caller that draws no fields sends no key, so nothing is required of it", () => {
    const request = quickReadBatchRequest({
      meter_no: "M-4021",
      read_date: "2026-07-05",
      notes: "",
      cycleId: null,
      registers: [{ channel: "total", reading: "1284" }],
    });
    expect(request.rows[0]).not.toHaveProperty("custom_data");
  });
});

describe("CR-161 W4 · New account (S18) sends the customer's answers inside the customer block", () => {
  it("lands on the customer, never on the account", () => {
    const payload = createAccountPayload({
      customer: {
        ...emptyCustomerForm(),
        full_name: "Elena Rivera",
        customer_custom_data: { preferred_language: "Spanish" },
      },
      unit: { unit_id: "u-1", opened_at: "2026-08-15" },
      preferences: emptyPreferencesForm(),
      mode: "activate",
    });
    expect(payload.customer).toMatchObject({ custom_data: { preferred_language: "Spanish" } });
    expect(payload.custom_data).toEqual({});
  });
});

const ROW: CustomerRow = {
  id: "01a05a61-bedb-7607-90a5-53ace7bb0e8f",
  customer_no: "C-00417",
  display_name: "Alvarez, Rosa",
  kind: "person",
  external_ref: null,
  phone: "512-555-0142",
  identity: {
    date_of_birth: "1974-03-02",
    ssn_held: false,
    ssn_last4: null,
    driving_licence_held: false,
    driving_licence_last4: null,
    tax_id_held: false,
    tax_id_last4: null,
  },
  account_count: 1,
  accounts: [],
  custom_data: { preferred_language: "Spanish", loyalty_tier: "Gold" },
} as CustomerRow;

function editClient(fields: CustomFieldRegistryEntry[], patch: ReturnType<typeof vi.fn>): ApiClient {
  return {
    get: vi.fn((path: string, options?: { query?: Record<string, unknown> }) => {
      if (path === "/custom-fields") {
        expect(options?.query).toMatchObject({
          entity: "customers",
          screen: "CUSTOMER_EDIT",
          mode: "input",
        });
        return Promise.resolve({ data: { entity: "customers", fields } });
      }
      return Promise.resolve({ data: {} });
    }),
    patch,
  } as unknown as ApiClient;
}

describe("CR-161 W4 · Edit customer (CUSTOMER_EDIT)", () => {
  it("pre-fills the stored answer and sends only what changed", async () => {
    const patch = vi.fn(() =>
      Promise.resolve({ data: { ...ROW, accounts_updated: 0, account_ids: [] } }),
    );
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <CustomerEditDialog
          row={ROW}
          t={t}
          dateFormat="MM/DD/YYYY"
          client={editClient(
            [field({ key: "preferred_language", label: "Preferred language" })],
            patch,
          )}
          onClose={() => undefined}
          onSaved={() => undefined}
        />
      </QueryClientProvider>,
    );
    const box = await waitFor(() => {
      const found = document.querySelector<HTMLInputElement>('[id="custom_data.preferred_language"]');
      expect(found).not.toBeNull();
      return found as HTMLInputElement;
    });
    expect(box.value).toBe("Spanish");
    fireEvent.change(box, { target: { value: "French" } });
    fireEvent.click(document.querySelector<HTMLButtonElement>('button[type="submit"]') as HTMLButtonElement);
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    const [, body] = patch.mock.calls[0] as unknown as [string, Record<string, unknown>];
    // ONLY the changed answer — the Gold loyalty tier this dialog does not draw
    // is never sent back, so it can never be refused or wiped from here.
    expect(body.custom_data).toEqual({ preferred_language: "French" });
  });

  it("a utility with no customer fields sees the dialog unchanged, and still names the screen", async () => {
    const patch = vi.fn(() =>
      Promise.resolve({ data: { ...ROW, accounts_updated: 0, account_ids: [] } }),
    );
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <CustomerEditDialog
          row={{ ...ROW, custom_data: {} }}
          t={t}
          dateFormat="MM/DD/YYYY"
          client={editClient([], patch)}
          onClose={() => undefined}
          onSaved={() => undefined}
        />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(document.querySelector('[id="display_name"]')).not.toBeNull());
    expect(document.body.textContent).not.toContain(t("customFields.sectionHeadingFallback"));
    const name = document.querySelector<HTMLInputElement>('[id="display_name"]') as HTMLInputElement;
    fireEvent.change(name, { target: { value: "Alvarez, Rosita" } });
    fireEvent.click(document.querySelector<HTMLButtonElement>('button[type="submit"]') as HTMLButtonElement);
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    const [, body] = patch.mock.calls[0] as unknown as [string, Record<string, unknown>];
    expect(body).toEqual({ display_name: "Alvarez, Rosita", custom_data: {} });
  });
});
