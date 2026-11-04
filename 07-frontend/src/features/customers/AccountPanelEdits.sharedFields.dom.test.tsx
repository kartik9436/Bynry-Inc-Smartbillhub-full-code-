// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CUS-10253 — the account page's edit dialogs use the shared
//          customer fields (PO 2026-10-18, image 08-edit.png): the contact
//          dialog gains *Contact by* and the date picker and Move-in's rules
//          (phone required, format checks); the co-applicant dialog gains a
//          date of birth; the mailing dialog gains Apt / Unit and a state LIST,
//          and refuses a malformed ZIP.
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY CASE READS WHAT WAS SENT**, not what the box shows: a field that
// renders and never reaches the PATCH is hard-won law 2's dead UI.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";

import type { ApiClient } from "@/api/client";
import type { AccountDetail } from "@/api/endpoints";

import { AccountGroupPencil, AccountPanelEditDialog } from "./AccountPanelEdits";
import type { AccountOverviewGroup } from "./AccountPanelEdits";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(() => cleanup());

type Sent = { method: string; path: string; body: unknown }[];

function client(sent: Sent): ApiClient {
  const answer = <T,>(data: unknown) => ({ data: data as T, status: 200 });
  return {
    request: <T,>(path: string, options?: { method?: string; body?: unknown }) => {
      sent.push({ method: options?.method ?? "GET", path, body: options?.body });
      return Promise.resolve(answer<T>({}));
    },
    get: <T,>(path: string) => {
      if (path === "/custom-fields") return Promise.resolve(answer<T>({ entity: "", fields: [] }));
      return Promise.resolve(answer<T>({ results: [], page: 1, per: 200, total: 0 }));
    },
  } as unknown as ApiClient;
}

function detail(): AccountDetail {
  return {
    id: "a-1",
    account_no: "AC-2026-00031",
    contacts: [
      {
        id: "c-1",
        full_name: "Maria Lopez",
        email: "maria.lopez@example.com",
        phone: "(734) 555-0182",
        dob: "1988-04-12",
        gov_id_last4: null,
        is_primary: true,
        contact_by: "email",
        custom_data: {},
      },
      {
        id: "c-2",
        full_name: "Daniel Lopez",
        email: null,
        phone: null,
        dob: null,
        gov_id_last4: null,
        is_primary: false,
        custom_data: {},
      },
    ],
    addresses: [
      { id: "ad-1", kind: "mailing", line1: "PO Box 2210", line2: null, city: "Ypsilanti", state: "MI", postal_code: "48197", custom_data: {} },
    ],
    service_agreements: [],
    custom_data: {},
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

const box = (id: string) => document.querySelector(`#${id}`) as HTMLInputElement;
const save = () => screen.getByRole("button", { name: t("customers.account.edit.save") });
const patch = (sent: Sent) => sent.find((call) => call.method === "PATCH");

describe("DEF-CUS-10253 · the contact dialog (image 08's Edit customer)", () => {
  it("draws Contact by and the product's date picker, and sends what changed", async () => {
    const sent: Sent = [];
    const user = userEvent.setup();
    mount("customer", client(sent));
    expect(box("contact_contact_by").value).toBe("email");
    expect(box("contact_dob").type).toBe("text");
    expect(box("contact_dob").value).toBe("04/12/1988");
    await user.selectOptions(box("contact_contact_by"), "text");
    await user.clear(box("contact_email"));
    await user.type(box("contact_email"), "maria@example.org");
    await user.click(save());
    expect(patch(sent)?.path).toBe("/accounts/a-1/contact");
    expect(patch(sent)?.body).toEqual({ contact_by: "text", email: "maria@example.org" });
  });

  it("the phone is required and both contact boxes are format-checked — nothing is sent", async () => {
    const sent: Sent = [];
    const user = userEvent.setup();
    mount("customer", client(sent));
    await user.clear(box("contact_phone"));
    await user.click(save());
    expect(patch(sent)).toBeUndefined();
    expect(document.body.textContent).toContain(t("customers.customer.edit.phoneRequired"));
    await user.type(box("contact_phone"), "555-01");
    await user.clear(box("contact_email"));
    await user.type(box("contact_email"), "maria@");
    await user.click(save());
    expect(patch(sent)).toBeUndefined();
    expect(document.body.textContent).toContain(t("customers.form.phoneInvalid"));
    expect(document.body.textContent).toContain(t("customers.form.emailInvalid"));
  });
});

describe("DEF-CUS-10253 · the co-applicant dialog", () => {
  it("takes a date of birth in the picker and sends it", async () => {
    const sent: Sent = [];
    const user = userEvent.setup();
    mount("coApplicant", client(sent));
    await user.type(box("co_applicant_dob"), "09/30/1986");
    await user.type(box("co_applicant_phone"), "(734) 555-0144");
    await user.click(save());
    expect(patch(sent)?.body).toEqual({ dob: "1986-09-30", phone: "(734) 555-0144" });
  });
});

describe("DEF-CUS-10253 · the mailing dialog (image 08's Edit mailing address)", () => {
  it("has Apt / Unit and the state from a list, and sends every part", async () => {
    const sent: Sent = [];
    const user = userEvent.setup();
    mount("mailing", client(sent));
    // The state is CHOSEN from the list (the kit's searchable select of the
    // fifty states, `UsAddressFields`), never typed free.
    expect(box("mailing_state").getAttribute("role")).toBe("combobox");
    await user.type(box("mailing_line2"), "Suite 4");
    await user.clear(box("mailing_state"));
    await user.type(box("mailing_state"), "Ohio");
    await user.click(await screen.findByRole("option", { name: /Ohio/ }));
    await user.click(save());
    expect(patch(sent)?.body).toEqual({
      line1: "PO Box 2210",
      line2: "Suite 4",
      city: "Ypsilanti",
      state: "OH",
      postal_code: "48197",
    });
  });

  it("marks Street, City, State and ZIP required, as the drawing does; Apt / Unit is not", () => {
    mount("mailing", client([]));
    for (const id of ["mailing_line1", "mailing_city", "mailing_state", "mailing_postal_code"]) {
      expect(box(id).getAttribute("aria-required"), id).toBe("true");
    }
    expect(box("mailing_line2").getAttribute("aria-required")).toBeNull();
  });

  it("refuses a malformed ZIP and a missing city before anything is sent", async () => {
    const sent: Sent = [];
    const user = userEvent.setup();
    mount("mailing", client(sent));
    await user.clear(box("mailing_postal_code"));
    await user.type(box("mailing_postal_code"), "4819");
    await user.clear(box("mailing_city"));
    await user.click(save());
    expect(patch(sent)).toBeUndefined();
    expect(document.body.textContent).toContain(t("common.usAddress.zipFormat"));
  });
});

describe("DEF-CUS-10261 · every pencil on the account page has a name", () => {
  // The union `AccountOverviewGroup`, every member. i18next answers a missing
  // key with the key itself — a non-empty string — so the button rendered and
  // a screen reader announced `customers.account.edit.group.coApplicant`.
  const groups = [
    "account", "money", "service", "meters", "plan", "customerRecord", "billingPrefs",
    "unit", "bills", "usage", "customer", "coApplicant", "mailing", "deposit", "portal",
  ] as const;
  it.each(groups)("the %s pencil's label is in the catalogue", (group) => {
    expect(i18n.exists(`customers.account.edit.group.${group}`)).toBe(true);
  });

  it("the co-applicant pencil is found by its words", () => {
    render(<AccountGroupPencil group="coApplicant" t={t} roleReason={null} onEdit={() => undefined} />);
    expect(screen.getByRole("button", { name: "Edit co-applicant" })).toBeInTheDocument();
  });
});
