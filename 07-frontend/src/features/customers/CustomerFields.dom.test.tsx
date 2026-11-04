// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CUS-6356 · 6357 · 6358 · 6359 · 6360 — the Customer step the
//           move-in and New account share (CustomerFields.tsx)
// Rules:    OQ-CUS-12618 (sub-categories are the utility's reference data) ·
//           BR-CUS-067 · hard rule 8 · B14 rules 33, 43
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY:** a harness that starts with
// `showErrors` already true would see the refusal and never prove it waits for
// Continue — so the first case starts false and flips it; and a category that
// happens to HAVE children would draw a select whether or not the absence
// branch works — so the absence case picks one with none.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import type { Translator } from "@/features/tenancy/settingsShared";
import i18n from "@/i18n";

import { CustomerFields, customerStepProblem } from "./CustomerFields";
import { ACCOUNT_CATEGORIES_QUERY_KEY, ACCOUNT_SUBTYPES_QUERY_KEY } from "./customersShared";
import { emptyCustomerForm, mailingAddressFor } from "./NewAccountWizard";
import type { CustomerForm } from "./NewAccountWizard";

afterEach(cleanup);

const t: Translator = (key, params) => i18n.t(key, params);

function Harness(props: {
  initial?: Partial<CustomerForm>;
  showErrors?: boolean;
  onValue?: (value: CustomerForm) => void;
}) {
  const [value, setValue] = useState<CustomerForm>({ ...emptyCustomerForm(), ...props.initial });
  const [tried, setTried] = useState(props.showErrors ?? false);
  props.onValue?.(value);
  return (
    <>
      <CustomerFields
        values={value}
        onChange={setValue}
        t={t}
        showErrors={tried}
        dateFormat="DD-MMM-YY"
        timeZone="America/Chicago"
      />
      <button type="button" onClick={() => setTried(true)}>
        Continue
      </button>
    </>
  );
}

function mount(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  client.setQueryData(ACCOUNT_CATEGORIES_QUERY_KEY, {
    selectable: [
      { code: "residential", name: "Residential" },
      { code: "commercial", name: "Commercial" },
      { code: "agricultural", name: "Agricultural" },
    ],
    legacy: [],
  });
  client.setQueryData(ACCOUNT_SUBTYPES_QUERY_KEY, {
    results: [
      { id: "st-1", code: "church", name: "Church", parent_code: "commercial" },
      { id: "st-2", code: "hospital", name: "Hospital", parent_code: "commercial" },
    ],
  });
  render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

describe("CustomerFields — the one Customer step both wizards mount", () => {
  it("Category is a dropdown, and the sub-category follows it", async () => {
    const user = userEvent.setup();
    mount(<Harness initial={{ account_type: "residential" }} />);

    const category = screen.getByLabelText(/Category/, { selector: "select" });
    expect(category.tagName).toBe("SELECT");
    // A category with no sub-categories says so; it draws no empty control.
    expect(document.getElementById("account_subtype")).toBeNull();
    expect(screen.getByText("None for this category")).toBeInTheDocument();

    await user.selectOptions(category, "commercial");
    const sub = screen.getByLabelText("Sub-category");
    expect(sub.tagName).toBe("SELECT");
    expect([...(sub as HTMLSelectElement).options].map((o) => o.textContent)).toEqual([
      "No sub-category",
      "Church",
      "Hospital",
    ]);
  });

  it("nothing is red until Continue, then the refusal is in words", async () => {
    const user = userEvent.setup();
    mount(<Harness initial={{ account_type: "residential" }} />);
    expect(screen.queryByRole("alert")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    const alert = screen.getByRole("alert");
    expect(alert.textContent?.trim().length ?? 0).toBeGreaterThan(0);
  });

  it("Same as service address is checked by default and writes no mailing row", async () => {
    const user = userEvent.setup();
    let latest = emptyCustomerForm();
    mount(<Harness initial={{ account_type: "residential" }} onValue={(v) => (latest = v)} />);

    const same = screen.getByLabelText("Same as service address");
    expect(same).toBeChecked();
    expect(document.getElementById("mailing_line1")).toBeNull();
    expect(mailingAddressFor(latest)).toBeNull();

    await user.click(same);
    for (const id of ["mailing_line1", "mailing_line2", "mailing_city", "mailing_state", "mailing_postal_code"]) {
      expect(document.getElementById(id)).not.toBeNull();
    }
    await user.type(document.getElementById("mailing_line1") as HTMLElement, "PO Box 88");
    await user.type(document.getElementById("mailing_city") as HTMLElement, "Austin");
    // The kit's state picker is searchable: type, then pick the option.
    await user.type(document.getElementById("mailing_state") as HTMLElement, "Tex");
    await user.click(document.getElementById("mailing_state-opt-TX") as HTMLElement);
    await user.type(document.getElementById("mailing_postal_code") as HTMLElement, "7870");
    // Four digits is not a ZIP code.
    expect(customerStepProblem({ ...latest, full_name: "Ana", phone: "5125550100", customer_kind: "person" })).toBe(
      "customers.account.mailingZipInvalid",
    );
    await user.type(document.getElementById("mailing_postal_code") as HTMLElement, "4");
    expect(mailingAddressFor(latest)).toEqual({
      kind: "mailing",
      line1: "PO Box 88",
      city: "Austin",
      state: "TX",
      postal_code: "78704",
    });
  });

  it("Date of birth is typed in the utility's format and stored as ISO", async () => {
    const user = userEvent.setup();
    let latest = emptyCustomerForm();
    mount(<Harness initial={{ account_type: "residential" }} onValue={(v) => (latest = v)} />);
    const dob = document.getElementById("dob") as HTMLInputElement;
    expect(dob.getAttribute("placeholder") ?? "").toMatch(/DD-MMM-YY/);
    await user.type(dob, "14-Mar-87");
    await user.tab();
    expect(latest.dob).toBe("1987-03-14");
  });
});
