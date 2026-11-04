// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   lane CF-1 (2026-10-18), tasks 3, 5, 6, 8, 9, 10 — the SHARED
//           customer form's pieces, each proved on its own: Who, Identity,
//           More about the customer, the co-owner words, Mailing address and
//           Preferences (customer-forms drawing set, images 01, 03, 06, 12–14).
// Rules:    decision log 2026-10-18 (Move-in's rules everywhere; Autopay only
//           where a payment method can be saved; every date a picker; phone
//           and email format checked) · B14 rules 33, 43
// ───────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { useState } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import { CoOwnerCards } from "../CoOwnerCards";
import type { CoOwnerDraft } from "../CoOwnerCards";
import { emptyCustomerForm } from "../NewAccountWizard";
import type { CustomerForm } from "../NewAccountWizard";
import { CustomerCustomFieldsPanel, customerCustomPayload } from "./CustomerCustomFieldsPanel";
import {
  CustomerIdentityPanel,
  CustomerWhoPanel,
  emailFormatProblem,
  emptyCustomerWhoExtras,
  phoneFormatProblem,
} from "./CustomerWhoPanel";
import type { CustomerWhoExtras } from "./CustomerWhoPanel";
import { MailingAddressBlock } from "./MailingAddressBlock";
import type { MailingAddressValue } from "./MailingAddressBlock";
import { PreferencesPanel } from "./PreferencesPanel";

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** A client that answers the reference reads every panel makes. */
const client = createApiClient({
  tenant: "annarbor",
  fetchImpl: async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/custom-fields")) {
      return json({
        entity: "customers",
        fields: url.includes("screen=S18")
          ? [
              { id: "f1", key: "medical_priority", label: "Medical priority", help_text: "", data_type: "text", options: [], is_required: false, display_order: 1, placement: {} },
              { id: "f2", key: "landlord_licence", label: "Landlord licence #", help_text: "", data_type: "text", options: [], is_required: false, display_order: 2, placement: {} },
            ]
          : [],
      });
    }
    if (url.includes("account-categories") || url.includes("categories")) {
      return json({ selectable: [{ code: "residential", name: "Residential" }], legacy: [] });
    }
    if (url.includes("shell/display")) return json({ regional: { language: "en" } });
    return json({ results: [], count: 0 });
  },
});

function wrap(node: ReactNode) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/annarbor/move-ins/new"]}>
        <Routes>
          <Route path="/:tenant/move-ins/new" element={node} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("format checks (task 10)", () => {
  it("a North American phone: ten digits, or eleven starting with 1, punctuation set aside", () => {
    expect(phoneFormatProblem("(734) 555-0182")).toBeNull();
    expect(phoneFormatProblem("+1 734.555.0182")).toBeNull();
    expect(phoneFormatProblem("")).toBeNull();
    expect(phoneFormatProblem("555-0182")).toBe("customers.form.phoneInvalid");
    expect(phoneFormatProblem("734 555 O182")).toBe("customers.form.phoneInvalid");
    expect(phoneFormatProblem("2 734 555 0182")).toBe("customers.form.phoneInvalid");
  });
  it("an email: blank is fine (optional everywhere), a malformed one is not", () => {
    expect(emailFormatProblem("")).toBeNull();
    expect(emailFormatProblem("maria.lopez@example.com")).toBeNull();
    expect(emailFormatProblem("maria.lopez@example")).toBe("customers.form.emailInvalid");
    expect(emailFormatProblem("maria lopez@example.com")).toBe("customers.form.emailInvalid");
  });
});

function WhoHost(props: { title: string; showCategory?: boolean; showErrors?: boolean; seed?: Partial<CustomerForm> }) {
  const [customer, setCustomer] = useState<CustomerForm>({ ...emptyCustomerForm(), customer_kind: "person", ...props.seed });
  const [extras, setExtras] = useState<CustomerWhoExtras>(emptyCustomerWhoExtras());
  return (
    <>
      <CustomerWhoPanel
        title={props.title}
        customer={customer}
        onCustomer={setCustomer}
        extras={extras}
        onExtras={(patch) => setExtras({ ...extras, ...patch })}
        showCategory={props.showCategory}
        showErrors={props.showErrors}
        t={t}
        dateFormat="MM/DD/YYYY"
        timeZone="America/Detroit"
      />
      <CustomerIdentityPanel customer={customer} onCustomer={setCustomer} t={t} />
      <output data-state="">{JSON.stringify({ customer, extras })}</output>
    </>
  );
}

const state = () => JSON.parse(document.querySelector("[data-state]")?.textContent ?? "{}");

describe("Who and Identity (task 3)", () => {
  it("the host names the panel; the person's fields are the drawn ones, and every one lands", () => {
    wrap(<WhoHost title={t("customers.moveIn.customer.whoTitle")} />);
    expect(screen.getByRole("heading", { name: t("customers.moveIn.customer.whoTitle") })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(new RegExp(`^${t("customers.account.field.fullName")}`)), { target: { value: "Maria Lopez" } });
    fireEvent.change(screen.getByLabelText(t("customers.account.field.email")), { target: { value: "maria.lopez@example.com" } });
    fireEvent.change(screen.getByLabelText(new RegExp(`^${t("customers.account.field.phone")}`)), { target: { value: "(734) 555-0182" } });
    fireEvent.change(document.getElementById("contact_by") as HTMLSelectElement, { target: { value: "text" } });
    fireEvent.change(document.getElementById("ssn") as HTMLInputElement, { target: { value: "123-45-4471" } });
    fireEvent.change(document.getElementById("driving_licence") as HTMLInputElement, { target: { value: "MI L-552-118-903" } });
    fireEvent.change(document.getElementById("gov_id_last4") as HTMLInputElement, { target: { value: "9001" } });
    const s = state();
    expect(s.customer).toMatchObject({
      full_name: "Maria Lopez",
      email: "maria.lopez@example.com",
      phone: "(734) 555-0182",
      ssn: "123-45-4471",
      driving_licence: "MI L-552-118-903",
      gov_id_last4: "9001",
    });
    expect(s.extras.contact_by).toBe("text");
    // The date of birth is the kit's picker, never a typed box (PO 2026-10-18).
    expect(document.querySelector('[id="dob"]')?.closest("[data-date-picker], .field")).not.toBeNull();
    expect(screen.getByText(t("customers.moveIn.customer.lastFourHelp"))).toBeInTheDocument();
    expect(screen.getByText(t("customers.form.oneIdRule"))).toBeInTheDocument();
  });

  it("a malformed phone and email are refused by name once Continue was pressed", () => {
    wrap(<WhoHost title="Who is applying" showErrors seed={{ full_name: "Maria", phone: "555-01", email: "maria@" }} />);
    expect(screen.getByText(t("customers.form.phoneInvalid"))).toBeInTheDocument();
    expect(screen.getByText(t("customers.form.emailInvalid"))).toBeInTheDocument();
  });

  it("showCategory=false asks no category (the portal's form)", () => {
    wrap(<WhoHost title="Who is applying" showCategory={false} />);
    expect(document.querySelector("[data-customer-category]")).toBeNull();
  });

  it("a company asks the legal name and Tax ID in Who", () => {
    wrap(<WhoHost title="Who will own the account" seed={{ customer_kind: "company" }} />);
    expect(screen.getByLabelText(new RegExp(`^${t("customers.moveIn.customer.legalName")}`))).toBeInTheDocument();
    expect(document.getElementById("tax_id")).not.toBeNull();
    expect(document.getElementById("dob")).toBeNull();
  });
});

describe("More about the customer (task 5, DEF-CUS-10224)", () => {
  it("draws the utility's fields under its own heading and hands back every answer", async () => {
    function Host() {
      const [values, setValues] = useState<Record<string, unknown>>({});
      return (
        <>
          <CustomerCustomFieldsPanel screen="S18" values={values} onChange={setValues} t={t} client={client} />
          <output data-state="">{JSON.stringify(values)}</output>
        </>
      );
    }
    wrap(<Host />);
    await waitFor(() => expect(screen.getByLabelText(/Medical priority/)).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: t("customers.form.moreAbout") })).toBeInTheDocument();
    expect(screen.getByText(t("customers.form.utilityFields"))).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Medical priority/), { target: { value: "No" } });
    fireEvent.change(screen.getByLabelText(/Landlord licence/), { target: { value: "LL-77" } });
    expect(JSON.parse(document.querySelector("[data-state]")?.textContent ?? "{}")).toEqual({
      medical_priority: "No",
      landlord_licence: "LL-77",
    });
  });

  it("a slot with no fields draws nothing at all", async () => {
    wrap(<CustomerCustomFieldsPanel screen="REQUEST_NEW" values={{}} onChange={() => undefined} t={t} client={client} />);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(document.querySelector('[data-customer-panel="custom"]')).toBeNull();
  });

  it("only answered keys are sent", () => {
    expect(customerCustomPayload({ a: "", b: "x", c: null, d: [], e: ["y"] })).toEqual({ b: "x", e: ["y"] });
    expect(customerCustomPayload({ a: "" })).toBeUndefined();
  });
});

describe("the co-owner card's words (task 6)", () => {
  for (const [label, title, tick, add] of [
    ["co_owner", "customers.moveIn.customer.coOwners.title", "customers.moveIn.customer.coOwners.tick", "customers.moveIn.customer.coOwners.add"],
    ["co_applicant", "customers.form.coApplicants.title", "customers.form.coApplicants.tick", "customers.form.coApplicants.add"],
    ["co_buyer", "customers.form.coBuyers.title", "customers.form.coBuyers.tick", "customers.form.coBuyers.add"],
  ] as const) {
    it(`${label}: its own heading, tick and add button`, () => {
      function Host() {
        const [rows, setRows] = useState<CoOwnerDraft[]>([]);
        const [on, setOn] = useState(false);
        return (
          <CoOwnerCards
            kind="co_owner"
            label={label}
            enabled={on}
            onEnabledChange={setOn}
            rows={rows}
            onChange={setRows}
            t={t}
            dateFormat="MM/DD/YYYY"
            timeZone="America/Detroit"
            showErrors={false}
          />
        );
      }
      wrap(<Host />);
      expect(screen.getByRole("heading", { name: t(title) })).toBeInTheDocument();
      fireEvent.click(screen.getByLabelText(t(tick)));
      expect(screen.getByRole("button", { name: t(add) })).toBeInTheDocument();
      expect(document.getElementById("co_owner_0_responsible_for_bills")?.tagName).toBe("SELECT");
    });
  }
});

describe("Mailing address (task 8)", () => {
  it("ticked shows the service address; unticked opens the US fields and every part lands", () => {
    function Host() {
      const [value, setValue] = useState<MailingAddressValue>({
        mailing_same: true, mailing_line1: "", mailing_line2: "", mailing_city: "", mailing_state: "", mailing_postal_code: "",
      });
      return (
        <>
          <MailingAddressBlock value={value} onChange={(patch) => setValue({ ...value, ...patch })} serviceAddress="143 Willow Bend Dr, Ann Arbor, MI 48108" t={t} />
          <output data-state="">{JSON.stringify(value)}</output>
        </>
      );
    }
    wrap(<Host />);
    expect(document.querySelector('[data-mailing="service"]')?.textContent).toContain("143 Willow Bend Dr");
    fireEvent.click(screen.getByLabelText(t("customers.account.field.mailingSame")));
    fireEvent.change(document.getElementById("mailing_line1") as HTMLInputElement, { target: { value: "PO Box 2210" } });
    fireEvent.change(document.getElementById("mailing_city") as HTMLInputElement, { target: { value: "Ypsilanti" } });
    fireEvent.change(document.getElementById("mailing_state") as HTMLInputElement, { target: { value: "Mich" } });
    fireEvent.click(document.getElementById("mailing_state-opt-MI") as HTMLElement);
    fireEvent.change(document.getElementById("mailing_postal_code") as HTMLInputElement, { target: { value: "48197" } });
    expect(JSON.parse(document.querySelector("[data-state]")?.textContent ?? "{}")).toMatchObject({
      mailing_same: false, mailing_line1: "PO Box 2210", mailing_city: "Ypsilanti", mailing_state: "MI", mailing_postal_code: "48197",
    });
  });
});

describe("Preferences (task 9)", () => {
  it("a request: paperless, text reminders, language — and no Autopay", () => {
    wrap(
      <PreferencesPanel on onTick={() => undefined} value={{ paperless: true, sms_reminders: false, autopay: false, preferred_language: "en" }} onChange={() => undefined} showAutopay={false} t={t} client={client} />,
    );
    expect(document.getElementById("paperless")).not.toBeNull();
    expect(document.getElementById("sms_reminders")).not.toBeNull();
    expect(document.getElementById("autopay")).toBeNull();
  });
  it("Move-in and New connect: Autopay first, as drawn", () => {
    wrap(
      <PreferencesPanel on onTick={() => undefined} value={{ paperless: false, sms_reminders: false, autopay: false, preferred_language: "en" }} onChange={() => undefined} showAutopay t={t} client={client} />,
    );
    const ids = Array.from(document.querySelectorAll("select")).map((el) => el.id);
    expect(ids.slice(0, 3)).toEqual(["autopay", "paperless", "sms_reminders"]);
  });
});
