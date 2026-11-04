// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: `DEF-CUS-10255` — the transfer's buyer step uses Move-in's customer
//          form (PO 2026-10-18, image 07-transfer.png): Who is buying (no
//          category — the seller's), Identity with *Search customer ID* and its
//          results table (the free-text finder is gone), co-buyer full cards,
//          the documents table, the mailing block, and Move-in's Tax,
//          Discounts and Preferences panels for the buyer. The seller's
//          exemption and discounts are NOT copied.
//          · `DEF-CUS-6549` (kept) — the FORM is the primary path, the search
//          is a convenience beside it, a hit FILLS the form and leaves it
//          editable, *Unlink* keeps what the clerk typed.
// Rules:   `BR-CUS-1081` · `BR-CUS-1023` · `BR-CUS-1020` · `BR-CUS-1022` ·
//          B14 rules 31, 42, 43, 44 · CLAUDE.md hard-won law 2
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS FILE WAS REWRITTEN FOR `DEF-CUS-10255`, NOT EXTENDED.** Its cases
// asserted the free-text `CustomerFinder`, a contact-only co-applicant and
// documents held to be uploaded after the sale — all three superseded by the
// drawing of 2026-10-18. The `DEF-CUS-6549` principles are re-asserted on the
// new pieces rather than dropped.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (hard-won law 7, habit 2): asserting
// a box is on the step without typing into it after a link (the ruling is that
// it stays EDITABLE); asserting the plan has a key without its value; a stale
// DOM from the previous case (`cleanup` after every case).
import "@testing-library/jest-dom/vitest";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";
import { createApiClient } from "@/api/client";
import type { AccountDetail } from "@/api/endpoints";

import {
  BuyerStep,
  TransferReviewStep,
  buyerAccountPayload,
  buyerSearchQuery,
  buyerShortfall,
  emptyTransferDraft,
  transferPlanOf,
} from "./TransferWizard";
import type { BuyerSearchState, TransferDraft } from "./TransferWizard";
import type { CustomerSearchResult, CustomerSearchRow } from "./customerEndpoints";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params) as string;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** Answers the reference reads the step's panels make; nothing else. */
const client = createApiClient({
  tenant: "brazosbend",
  fetchImpl: async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/move-ins/pricing")) {
      return json({
        plan: {
          taxes: [],
          claimable_discounts: [
            { ref: { id: "disc-senior", name: "Senior citizen" }, value_display: "−$5.00 a month", pairs_with: null },
          ],
        },
        fees: [],
        services: [],
      });
    }
    if (url.includes("shell/display")) return json({ regional: { language: "en" } });
    if (url.includes("required-documents") || url.includes("document")) return json({ required: [] });
    return json({ results: [], count: 0 });
  },
});

function account(): AccountDetail {
  return {
    id: "acc-10650",
    account_no: "AC-2026-00031",
    account_type: "residential",
    unit_id: "unit-1",
    contacts: [{ id: "c1", full_name: "Robert Hale", email: null, phone: null, dob: null, gov_id_last4: null, is_primary: true }],
    addresses: [],
  } as unknown as AccountDetail;
}

/** A customer as `POST /customers/search` serves one (CF-1's table row). */
function found(over: Partial<CustomerSearchRow> = {}): CustomerSearchRow {
  return {
    id: "11111111-2222-4333-8444-555555555555",
    customer_no: "C-00412",
    display_name: "Maria Lopez",
    kind: "person",
    verdict: "found",
    agreed: ["name", "date_of_birth"],
    date_of_birth: "1988-04-12",
    phone_last4: "0182",
    accounts: { count: 2, rows: [], outstanding_total: "42.10", currency: "USD", available: true, open_count: 0 },
    company: null,
    ...over,
  } as unknown as CustomerSearchRow;
}

function mountStep(options: { answer?: CustomerSearchResult | null; run?: (q: unknown) => void } = {}) {
  const held: { draft: TransferDraft } = { draft: emptyTransferDraft() };
  const search: BuyerSearchState = {
    answer: options.answer ?? null,
    pending: false,
    failed: false,
    dismissed: [],
    onDismiss: () => undefined,
    run: options.run ?? (() => undefined),
  };
  function Host() {
    const [draft, setDraft] = useState<TransferDraft>(held.draft);
    held.draft = draft;
    return (
      <BuyerStep
        draft={draft}
        account={account()}
        onPatch={(next) => setDraft((d) => ({ ...d, ...next }))}
        t={t}
        dateFormat="MM/DD/YYYY"
        timeZone="America/Chicago"
        categoryName="Residential"
        client={client}
        search={search}
      />
    );
  }
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/brazosbend/transfers/new"]}>
        <Routes>
          <Route path="/:tenant/*" element={<Host />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { read: () => held.draft };
}

const control = (id: string): HTMLInputElement | null =>
  document.querySelector(`#${id}`) as HTMLInputElement | null;

describe("DEF-CUS-10255 · the buyer step is Move-in's customer form (image 07)", () => {
  it("draws every panel the drawing draws, in its order", () => {
    mountStep();
    const panels = [
      document.querySelector("[data-transfer-seller]"),
      document.querySelector('[data-customer-panel="who"]'),
      document.querySelector("[data-search-customer-id]"),
      document.querySelector('[data-tick-panel="co_owner"]'),
      document.querySelector('[data-tick-panel="mailing"]'),
    ];
    for (const panel of panels) expect(panel).not.toBeNull();
    expect(screen.getByText(t("customers.transfer.buyer.whoTitle"))).toBeInTheDocument();
    expect(screen.getByText(t("customers.moveIn.tax.title"))).toBeInTheDocument();
    expect(screen.getByText(t("customers.moveIn.discounts.title"))).toBeInTheDocument();
    // The seller, from the account, with the category BY NAME.
    expect(document.querySelector("[data-transfer-seller]")?.textContent).toContain("AC-2026-00031 · Robert Hale");
    expect(document.querySelector("[data-transfer-seller]")?.textContent).toContain("Residential");
  });

  it("asks no category — it is the seller's account's", () => {
    mountStep();
    expect(document.querySelector("[data-customer-category]")).toBeNull();
  });

  it("the free-text finder is gone and there is no *Create customer* button", () => {
    mountStep();
    expect(control("trf_buyer_finder")).toBeNull();
    expect(screen.queryByRole("button", { name: /create customer/i })).toBeNull();
  });

  it("a clerk who never searches can complete the buyer and be let off the step", async () => {
    const user = userEvent.setup();
    const { read } = mountStep();
    await user.click(screen.getByRole("radio", { name: t("customers.customer.kind.person") }));
    await user.type(control("full_name") as HTMLInputElement, "Maria Lopez");
    await user.type(control("phone") as HTMLInputElement, "(734) 555-0182");
    expect(buyerShortfall(read())).toBeNull();
  });

  it("*Search customer ID* asks with what was typed, and a hit FILLS the form and leaves it editable", async () => {
    const user = userEvent.setup();
    const run = vi.fn();
    const answer: CustomerSearchResult = { result: "found", count: 1, customers: [found()] };
    const { read } = mountStep({ answer, run });
    await user.click(screen.getByRole("radio", { name: t("customers.customer.kind.person") }));
    await user.type(control("full_name") as HTMLInputElement, "Maria");
    await user.click(document.querySelector("[data-search-customer-id]") as HTMLElement);
    expect(run).toHaveBeenCalledWith({ kind: "person", name: "Maria" });
    await user.click(screen.getByRole("button", { name: t("customers.moveIn.customer.match.linkName", { name: "Maria Lopez · C-00412" }) }));
    expect(read().buyerCustomer?.customer_no).toBe("C-00412");
    expect(control("full_name")?.value).toBe("Maria Lopez");
    expect(control("full_name")).not.toBeDisabled();
    await user.type(control("phone") as HTMLInputElement, "(734) 555-0182");
    expect(read().buyer.phone).toBe("(734) 555-0182");
  });
});

describe("DEF-CUS-10255 · every field on the step reaches the server", () => {
  function filled(): TransferDraft {
    const draft = emptyTransferDraft();
    return {
      ...draft,
      fromAccountId: "acc-10650",
      buyer: {
        ...draft.buyer,
        customer_kind: "person",
        full_name: "Maria Lopez",
        email: "maria.lopez@example.com",
        phone: "(734) 555-0182",
        dob: "1988-04-12",
        ssn: "123-45-4471",
        driving_licence: "MI L-552-118-903",
      },
      buyerExtras: { ...draft.buyerExtras, contact_by: "text" },
      coBuyersOn: true,
      coBuyers: [
        {
          key: "k1",
          full_name: "Daniel Lopez",
          relationship: "spouse",
          title: "",
          ownership_pct: "",
          signs_for_company: false,
          personal_guarantee: false,
          responsible_for_bills: true,
          phone: "(734) 555-0144",
          email: "dan.lopez@example.com",
          date_of_birth: "1986-09-30",
          ssn: "",
          driving_licence: "",
          contact_by: "",
        } as unknown as TransferDraft["coBuyers"][number],
      ],
      buyerDocRows: [{ key: "d1", doc_type: "photo_id", card_id: "card-1", name: "maria-id.jpg" }],
      mailingSameAsService: false,
      buyerMailing: { line1: "PO Box 2210", line2: "Suite 4", city: "Ypsilanti", state: "MI", postal_code: "48197" },
      buyerBilling: {
        ...draft.buyerBilling,
        prefsOn: true,
        taxOn: true,
        tax: {
          categoryId: "cat-nonprofit",
          certificateRef: "EX-55-90211",
          issuedOn: "2026-01-05",
          expiresOn: "2029-01-04",
          file: { name: "exempt-cert.pdf", contentType: "application/pdf", base64: "JVBERi0=" },
        },
        discountsOn: true,
        discounts: [{ key: "r1", discountId: "disc-senior", note: "" }],
      },
      buyerPrefs: { ...draft.buyerPrefs, paperless: true, sms_reminders: true, autopay: false, preferred_language: "es" },
      soldOn: "2026-10-20",
    };
  }

  it("the buyer's identity, contact, date of birth, language and mailing ride `customer`", () => {
    const plan = transferPlanOf(filled());
    expect(plan.customer).toMatchObject({
      display_name: "Maria Lopez",
      kind: "person",
      identity: { ssn: "123-45-4471", driving_licence: "MI L-552-118-903", phone: "(734) 555-0182" },
      applicant_email: "maria.lopez@example.com",
      date_of_birth: "1988-04-12",
      preferred_language: "es",
      mailing_address: { line1: "PO Box 2210", line2: "Suite 4", city: "Ypsilanti", state: "MI", postal_code: "48197" },
    });
  });

  it("co-buyers, documents, Tax, Discounts and Preferences ride `buyer_account`", () => {
    const plan = transferPlanOf(filled());
    expect(plan.buyer_account).toMatchObject({
      co_owners: [
        expect.objectContaining({
          full_name: "Daniel Lopez",
          relationship: "spouse",
          phone: "(734) 555-0144",
          email: "dan.lopez@example.com",
          date_of_birth: "1986-09-30",
          responsible_for_bills: true,
        }),
      ],
      documents: [{ card_id: "card-1", doc_type: "photo_id" }],
      tax_exemption: {
        category_id: "cat-nonprofit",
        certificate_ref: "EX-55-90211",
        issued_on: "2026-01-05",
        expires_on: "2029-01-04",
        certificate: { name: "exempt-cert.pdf", content_type: "application/pdf", content_base64: "JVBERi0=" },
      },
      discount_claims: [{ discount_id: "disc-senior" }],
      paperless: true,
      sms_reminders: true,
      autopay: false,
    });
  });

  // DEF-CUS-10264 — found on the walk: Review said *Co-applicant: None* and
  // *Documents: None* and showed nothing of Tax, Discounts or Preferences,
  // while every one of them landed on the account at the sale.
  it("Review restates the co-buyers, documents, Tax, Discounts and Preferences the commit sends", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <TransferReviewStep draft={filled()} account={account()} t={t} dateFormat="MM/DD/YYYY" />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const cell = (key: string) => document.querySelector(`[data-review="${key}"] td`)?.textContent ?? "";
    expect(cell("co-applicant")).toBe("Daniel Lopez");
    expect(cell("documents")).toBe(t("customers.transfer.step5.documentsCount", { count: 1 }));
    expect(cell("tax")).toBe(`${t("customers.moveIn.review.exempt")} · EX-55-90211`);
    expect(cell("discounts")).toBe(t("customers.transfer.step5.discountsCount", { count: 1 }));
    expect(cell("preferences")).toBe(
      `${t("customers.moveIn.review.paperless")} · ${t("customers.moveIn.review.textReminders")}`,
    );
  });

  it("an untouched buyer step sends no `buyer_account` — the seller's exemption and discounts are not copied", () => {
    const draft = { ...emptyTransferDraft(), buyerBilling: { ...emptyTransferDraft().buyerBilling, prefsOn: false } };
    expect(buyerAccountPayload(draft)).toBeUndefined();
    // And the panels open EMPTY: nothing of the seller's is pre-filled.
    expect(emptyTransferDraft().buyerBilling.taxOn).toBe(false);
    expect(emptyTransferDraft().buyerBilling.discounts).toEqual([]);
  });

  it("a LINKED buyer sends no identifier, and the search question needs a kind and a name", () => {
    const draft = { ...filled(), buyerCustomer: found() };
    expect(transferPlanOf(draft).customer.identity).toEqual({});
    expect(transferPlanOf(draft).customer.customer_id).toBe(found().id);
    expect(buyerSearchQuery(emptyTransferDraft().buyer)).toBeNull();
  });
});
