// ── Trace ──────────────────────────────────────────────
// Change:   BR-CUS-1054 — a customer's own details can be corrected.
//           `CR-094-BRC01` wave R.
// Rules:    BR-CUS-1054 · BR-CUS-054 (one email correction reaches every
//           account) · BR-CUS-1022 (a company has no date of birth) ·
//           CLAUDE.md hard rule 4 (issued bills do not restate) · hard-won
//           law 2 (built is not wired — and its mirror, a live screen behind a
//           dead control) · B14 rule 15 · rule 33
// ───────────────────────────────────────────────────────
//
// ⚠ **THE CASE THAT MATTERS MOST HERE IS `customerChanges`, NOT THE MARKUP.**
// An absent key means *leave it alone* and `""` means *clear it*, so a dialog
// that posted its whole form back would turn every untouched blank into a
// deliberate erasure — and on `phone` that erases the customer from the search
// box with nothing on screen to show for it. A DOM assertion cannot see which
// keys were sent, so the function is exported and driven directly.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { CUSTOMER_KIND_COMPANY, CustomerEditDialog, customerChanges } from "./CustomerEditDialog";
import type { CustomerFormValues } from "./CustomerEditDialog";
import type { CustomerRow } from "./customerEndpoints";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function row(over: Partial<CustomerRow> = {}): CustomerRow {
  return {
    id: "01a05a61-bedb-7607-90a5-53ace7bb0e8f",
    customer_no: "C-00417",
    display_name: "Alvarez, Rosa",
    kind: "person",
    external_ref: null,
    phone: "512-555-0142",
    identity: {
      date_of_birth: "1974-03-02",
      ssn_held: true,
      ssn_last4: "6789",
      driving_licence_held: true,
      driving_licence_last4: "4417",
      tax_id_held: false,
      tax_id_last4: null,
    },
    account_count: 2,
    accounts: [],
    ...over,
  };
}

function values(over: Partial<CustomerFormValues> = {}): CustomerFormValues {
  return {
    display_name: "Alvarez, Rosa",
    external_ref: "",
    date_of_birth: "1974-03-02",
    phone: "512-555-0142",
    email: "",
    contact_by: "",
    ssn: "",
    driving_licence: "",
    tax_id: "",
    ...over,
  };
}

function markup(over: Partial<CustomerRow> = {}): string {
  // `CR-161-BRC10` W4 — the dialog now draws the utility's own customer fields
  // through the shared `CustomFieldsInput`, which reads its registry through
  // react-query; the app mounts every dialog inside the provider, so does this.
  return renderToStaticMarkup(
    <QueryClientProvider client={new QueryClient()}>
      <CustomerEditDialog
        row={row(over)}
        t={t}
        dateFormat="MM/DD/YYYY"
        onClose={() => undefined}
        onSaved={() => undefined}
      />
    </QueryClientProvider>,
  );
}

describe("BR-CUS-1054 — what the dialog sends", () => {
  it("sends nothing at all when nothing was touched", () => {
    expect(customerChanges(row(), values())).toEqual({});
  });

  it("sends only the field the clerk actually changed", () => {
    expect(customerChanges(row(), values({ display_name: "Alvarez, Rosita" }))).toEqual({
      display_name: "Alvarez, Rosita",
    });
  });

  it("never sends the blank email the field always opens with", () => {
    // `contacts.email` hangs off the ACCOUNT, so the customer row carries none
    // and the field opens empty on every customer. An untouched blank must not
    // read as *clear the email on every account they hold*.
    expect(customerChanges(row(), values())).not.toHaveProperty("email");
    expect(customerChanges(row(), values({ email: "rosa@example.test" }))).toEqual({
      email: "rosa@example.test",
    });
  });

  it("sends an emptied phone as an empty string, because clearing is a real act", () => {
    expect(customerChanges(row(), values({ phone: "" }))).toEqual({ phone: "" });
  });

  it("never sends a date of birth for a company", () => {
    // `BR-CUS-1022` — a company has none, and the server refuses it BY NAME.
    // The form does not offer what the server will refuse, so nothing can
    // arrive from a stale value left in state.
    const company = row({ kind: CUSTOMER_KIND_COMPANY, display_name: "Kulkarni Holdings LLC" });
    const changed = customerChanges(company, values({ date_of_birth: "1999-01-01" }));
    expect(changed).not.toHaveProperty("date_of_birth");
  });
});

describe("BR-CUS-1054 — what the dialog draws", () => {
  it("draws the five fields a clerk came here for", () => {
    const html = markup();
    for (const label of [
      "customers.customer.edit.name",
      "customers.customer.edit.ref",
      "customers.customer.edit.dob",
      "customers.customer.edit.phone",
      "customers.customer.edit.email",
    ]) {
      expect(html).toContain(t(label));
    }
  });

  it("says what a correction does and does not do", () => {
    // Hard rule 4: the customer name is locked into a bill's snapshot at issue,
    // so a correction changes the NEXT bill and nothing already sent. And the
    // portal sign-in is a different column in another module. Both are things a
    // clerk would otherwise learn from an angry customer.
    expect(markup()).toContain(t("customers.customer.edit.effectBody"));
  });

  it("draws no date of birth for a company", () => {
    const html = markup({ kind: CUSTOMER_KIND_COMPANY, display_name: "Kulkarni Holdings LLC" });
    expect(html).not.toContain(t("customers.customer.edit.dob"));
  });

  it("names the customer rather than the row key (B14 rule 31)", () => {
    const html = markup();
    expect(html).toContain("Alvarez, Rosa");
    expect(html).not.toContain("01a05a61-bedb-7607-90a5-53ace7bb0e8f");
  });

  // ⊕ `DEF-CUS-10253` (image 08-edit.png) — the dialog now OFFERS the SSN and
  // the licence, so the case that asserted it drew no spelling of them is
  // replaced by what `BR-CUS-092(c)` actually asks: the box opens EMPTY, the
  // last four on file is only its placeholder, and the full number is nowhere.
  it("draws the SSN and licence boxes empty, with only the last four as a hint", () => {
    const html = markup();
    expect(html).toContain('placeholder="•••-••-6789"');
    expect(html).toContain('placeholder="•••• 4417"');
    expect(html).toMatch(/id="ssn"[^>]*value=""/);
    expect(html).not.toContain("123456789");
  });

  it("draws image 08's fields: Person / Company, Contact by, and the date picker", () => {
    const html = markup();
    expect(html).toContain('data-segment="person"');
    expect(html).toContain('data-segment="company"');
    expect(html).toContain('id="contact_by"');
    expect(html).toContain('data-regional-date="MM/DD/YYYY"');
  });

  it("sends every field the clerk changed — contact by and a new SSN included", () => {
    const changes = customerChanges(
      row({ email: "rosa@example.com", contact_by: "email" } as Partial<CustomerRow>),
      values({ email: "rosa.alvarez@example.com", contact_by: "text", ssn: "123-45-6780", driving_licence: "TX 9988" }),
    );
    expect(changes).toEqual({
      email: "rosa.alvarez@example.com",
      contact_by: "text",
      ssn: "123-45-6780",
      driving_licence: "TX 9988",
    });
  });
});
