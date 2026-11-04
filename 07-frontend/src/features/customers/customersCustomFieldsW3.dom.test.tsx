// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 W3, customers lane — the screens for contacts, mailing
//          addresses and service agreements, and New Connection Step 1
// Defects: DEF-CUS-9159 · DEF-CUS-9168 · DEF-CUS-9169 · DEF-CUS-9170
// Rules:   BR-TEN-052 as amended 2026-10-02 · US-SHL-015 TC-4 (nothing at all
//          when the utility defined none) · B14 rules 31 and 43
// ───────────────────────────────────────────────────────
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { AccountDetail, CustomFieldRegistryEntry } from "@/api/endpoints";

import { AccountPanelEditDialog } from "./AccountPanelEdits";
import type { AccountOverviewGroup } from "./AccountPanelEdits";
import { sharedAgreementAnswers } from "./ChangePlanWizard";
import {
  createAccountPayload,
  emptyCustomerForm,
  emptyPreferencesForm,
  mailingAddressFor,
  serviceFieldsLostOnDraft,
} from "./NewAccountWizard";
import { commitPlanOf, emptyDraft } from "./newConnectDraft";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(() => cleanup());

function field(key: string, label: string, over: Partial<CustomFieldRegistryEntry> = {}) {
  return {
    id: `cf-${key}`,
    key,
    label,
    help_text: "",
    data_type: "text",
    options: [],
    is_required: false,
    display_order: 0,
    placement: { S21: "input" },
    ...over,
  } as CustomFieldRegistryEntry;
}

/** Answers the registry read with `fields` for `entity` and remembers every call. */
function client(
  sent: { method: string; path: string; body: unknown }[],
  entity: string,
  fields: CustomFieldRegistryEntry[],
): ApiClient {
  const answer = <T,>(data: unknown) => ({ data: data as T, status: 200, headers: new Headers() });
  return {
    request: <T,>(path: string, options?: { method?: string; body?: unknown }) => {
      sent.push({ method: options?.method ?? "GET", path, body: options?.body });
      return Promise.resolve(answer<T>({}));
    },
    get: <T,>(path: string, options?: { query?: Record<string, unknown> }) => {
      sent.push({ method: "GET", path, body: options?.query });
      if (path === "/custom-fields") {
        const wanted = options?.query?.entity === entity ? fields : [];
        return Promise.resolve(answer<T>({ entity: options?.query?.entity, fields: wanted }));
      }
      return Promise.resolve(answer<T>({ results: [], page: 1, per: 200, total: 0 }));
    },
  } as unknown as ApiClient;
}

function detail(over: Partial<AccountDetail> = {}): AccountDetail {
  return {
    id: "a-1",
    account_no: "AC-2026-00012",
    contacts: [
      {
        id: "c-1",
        full_name: "John Mauli",
        email: null,
        // ⊕ DEF-CUS-10253 — the account holder's phone is required on the
        // contact dialog now (Move-in's rule, image 08), so the fixture has one.
        phone: "(512) 555-0142",
        dob: null,
        gov_id_last4: null,
        is_primary: true,
        custom_data: { preferred_name: "Johnny" },
      },
    ],
    addresses: [
      {
        id: "ad-1",
        kind: "mailing",
        line1: "PO Box 12",
        city: "Austin",
        state: "TX",
        postal_code: "78701",
        custom_data: { delivery_note: "Side door" },
      },
    ],
    service_agreements: [],
    custom_data: {},
    ...over,
  } as unknown as AccountDetail;
}

function mount(group: AccountOverviewGroup, api: ApiClient) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AccountPanelEditDialog
        detail={detail()}
        group={group}
        client={api}
        t={t}
        dateFormat="MM/DD/YYYY"
        onClose={() => undefined}
        onSaved={() => undefined}
      />
    </QueryClientProvider>,
  );
}

describe("DEF-CUS-9168 · the contact edit on Account detail", () => {
  it("reads contacts' S21 input fields, opens on the stored answer and sends only the change", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    const user = userEvent.setup();
    mount(
      "customer",
      client(sent, "contacts", [
        field("preferred_name", "Preferred name"),
        field("best_time", "Best time"),
      ]),
    );
    const box = await screen.findByLabelText("Best time");
    expect(screen.getByLabelText("Preferred name")).toHaveValue("Johnny");
    expect(sent.find((call) => call.path === "/custom-fields")?.body).toEqual({
      entity: "contacts",
      screen: "S21",
      mode: "input",
    });
    await user.type(box, "Evenings");
    // The recap names the field by its LABEL, never its key (B14 rule 31).
    expect(screen.getAllByText("Best time").length).toBeGreaterThan(1);
    await user.click(screen.getByRole("button", { name: t("customers.account.edit.save") }));
    const patch = sent.find((call) => call.method === "PATCH");
    expect(patch?.path).toBe("/accounts/a-1/contact");
    expect(patch?.body).toEqual({ custom_data: { best_time: "Evenings" } });
  });

  it("a utility with no contact fields sees the dialog unchanged", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    mount("customer", client(sent, "contacts", []));
    await screen.findByLabelText(t("customers.account.field.fullName"), { exact: false });
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.queryByText(t("customFields.sectionHeadingFallback"))).toBeNull();
  });
});

describe("DEF-CUS-9169 · the mailing edit on Account detail", () => {
  it("sends the changed address answer beside the street", async () => {
    const sent: { method: string; path: string; body: unknown }[] = [];
    const user = userEvent.setup();
    mount(
      "mailing",
      client(sent, "addresses", [
        field("delivery_note", "Delivery note"),
        field("attention", "Attention"),
      ]),
    );
    await user.type(await screen.findByLabelText("Attention"), "Accounts");
    await user.click(screen.getByRole("button", { name: t("customers.account.edit.save") }));
    const patch = sent.find((call) => call.method === "PATCH");
    expect(patch?.path).toBe("/accounts/a-1/mailing-address");
    expect(patch?.body).toEqual({
      line1: "PO Box 12",
      // ⊕ DEF-CUS-10253 — Apt / Unit is on the dialog now (image 08).
      line2: "",
      city: "Austin",
      state: "TX",
      postal_code: "78701",
      custom_data: { attention: "Accounts" },
    });
  });

  it("New Account puts the address answers on the mailing row, and none when it is the service address", () => {
    const typed = {
      ...emptyCustomerForm(),
      mailing_same: false,
      mailing_line1: "PO Box 12",
      mailing_custom_data: { delivery_note: "Side door" },
    };
    expect(mailingAddressFor(typed)?.custom_data).toEqual({ delivery_note: "Side door" });
    expect(mailingAddressFor({ ...typed, mailing_same: true })).toBeNull();
    expect(mailingAddressFor({ ...typed, mailing_custom_data: {} })).not.toHaveProperty(
      "custom_data",
    );
  });
});

describe("DEF-CUS-9170 · service agreements", () => {
  const base = {
    customer: { ...emptyCustomerForm(), full_name: "Elena Rivera", account_type: "residential" },
    preferences: emptyPreferencesForm(),
  };

  it("an active create sends the unit step's answers; a draft sends none and the review says so", () => {
    const unit = {
      unit_id: "u-1",
      opened_at: "2026-10-01",
      service_custom_data: { contract_term: "12 months" },
    };
    expect(createAccountPayload({ ...base, unit, mode: "activate" }).service_custom_data).toEqual({
      contract_term: "12 months",
    });
    expect(createAccountPayload({ ...base, unit, mode: "draft" })).not.toHaveProperty(
      "service_custom_data",
    );
    expect(serviceFieldsLostOnDraft(unit, "draft")).toBe(true);
    expect(serviceFieldsLostOnDraft(unit, "activate")).toBe(false);
    expect(serviceFieldsLostOnDraft({ ...unit, service_custom_data: {} }, "draft")).toBe(false);
  });

  it("Change plan opens on the answers every OPEN agreement shares", () => {
    expect(
      sharedAgreementAnswers([
        { ended_on: null, custom_data: { term: "12", access: "Back yard" } },
        { ended_on: null, custom_data: { term: "12", access: "Front" } },
        { ended_on: "2026-01-01", custom_data: { term: "6" } },
      ]),
    ).toEqual({ term: "12" });
    expect(sharedAgreementAnswers([])).toEqual({});
  });
});

describe("DEF-CUS-9191 · New Account sends the account fields even when nothing was typed", () => {
  it("an untouched blob still travels, so a required field drawn there is checked", () => {
    const payload = createAccountPayload({
      customer: { ...emptyCustomerForm(), full_name: "Iris", account_type: "residential" },
      unit: { unit_id: "u-1", opened_at: "2026-10-01" },
      preferences: emptyPreferencesForm(),
      mode: "activate",
    });
    expect(payload.custom_data).toEqual({});
  });
});

describe("DEF-CUS-9159 · New Connection Step 1's account fields reach the commit", () => {
  it("the owner block carries what Step 1 typed", () => {
    const draft = { ...emptyDraft(), accountCustomData: { visit_window: "Mornings" } };
    expect(commitPlanOf(draft, null, []).owner.custom_data).toEqual({ visit_window: "Mornings" });
  });
});
