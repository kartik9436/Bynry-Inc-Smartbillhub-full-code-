// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   lane CF-1 (2026-10-18), task 13 — New Connection's owner step is
//           the shared customer form (drawing set `customer-forms-2026-10-18`,
//           image 06) and **the commit carries every value it asks**:
//           the mailing address (`DEF-CUS-10222`), *Contact by*, the
//           government ID, the co-owner CARDS, and — from a request — every
//           answer the request holds. The server half (the owner block reaches
//           the account) is `06-backend/tests/test_cf1_customer_forms_2026_10_18.py`.
// Rulings:  decision log *"2026-10-18 — CUSTOMER DATA AND UI CONSISTENT ACROSS
//           THE CREATE SCREENS"* — PO *"ALSO DATA COLECTED IS NOT LOST"*.
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY (law 7):** a case that built the
// payload itself would assert its own fixture. Every payload here is read
// through `commitPlanOf`, the function the Create press calls, and the DOM
// case reads back the draft the clerk's typing produced.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { coOwnerSummary, coOwnersPayload, emptyCoOwner } from "./CoOwnerCards";
import { ChargesStep } from "./NewConnectChargesStep";
import { DRAWN_DETAIL, DRAWN_PLAN_ID, DRAWN_SECTIONS } from "@/features/rating/planSections/thisPlanFixture";
import { ACCOUNT_CATEGORIES_QUERY_KEY, ACCOUNT_SUBTYPES_QUERY_KEY } from "./customersShared";
import {
  commitPlanOf,
  coOwnersFromRequest,
  draftFromRaisedBuild,
  emptyDraft,
  moveInExtrasProblems,
  ownerDocumentsToFile,
} from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";
import type { ConnectionDetail } from "./newConnectEndpoints";
import { OwnerScopeStep } from "./NewConnectOwnerStep";

const t = (key: string, params?: Record<string, unknown>): string =>
  String(i18next.t(key, params as never));

afterEach(cleanup);

const OWNER = {
  ...emptyDraft().owner,
  name: "Maria Lopez",
  partyKind: "person",
  phone: "(734) 555-0182",
  category: "residential",
};

describe("DEF-CUS-10222 · the mailing address reaches the owner's account", () => {
  it("unticked: one mailing row, in the accounts door's own words", () => {
    const draft: NewConnectDraft = {
      ...emptyDraft(),
      owner: OWNER,
      mailing: {
        sameAsService: false,
        address: "PO Box 2210",
        unit: "",
        city: "Ypsilanti",
        state: "MI",
        postalCode: "48197",
      },
    };
    expect(commitPlanOf(draft, null).owner).toMatchObject({
      addresses: [
        { kind: "mailing", line1: "PO Box 2210", city: "Ypsilanti", state: "MI", postal_code: "48197" },
      ],
    });
  });

  it("ticked (the bill goes to the building): an empty list, never omitted", () => {
    const owner = commitPlanOf({ ...emptyDraft(), owner: OWNER }, null).owner as Record<string, unknown>;
    expect(owner.addresses).toEqual([]);
  });
});

describe("the shared form's other answers travel", () => {
  it("Contact by and the government ID ride the owner block", () => {
    const owner = commitPlanOf(
      { ...emptyDraft(), owner: { ...OWNER, contactBy: "text", govIdLast4: "9001" } },
      null,
    ).owner;
    expect(owner).toMatchObject({ contact_by: "text", gov_id_last4: "9001" });
  });

  it("every co-owner card travels whole; a nameless card and an unticked panel do not", () => {
    const cards = [
      { ...emptyCoOwner(), full_name: "Daniel Lopez", relationship: "spouse", responsible_for_bills: true, phone: "(734) 555-0144" },
      { ...emptyCoOwner(), full_name: "Ana Lopez", relationship: "family" },
      { ...emptyCoOwner(), full_name: "  " },
    ];
    const on = commitPlanOf({ ...emptyDraft(), owner: OWNER, coOwnersOn: true, coOwners: cards }, null).owner;
    expect(on).toMatchObject({
      co_owners: [
        { full_name: "Daniel Lopez", relationship: "spouse", responsible_for_bills: true, phone: "(734) 555-0144" },
        { full_name: "Ana Lopez", relationship: "family" },
      ],
    });
    const off = commitPlanOf({ ...emptyDraft(), owner: OWNER, coOwnersOn: false, coOwners: cards }, null).owner;
    expect(off).not.toHaveProperty("co_owners");
  });

  it("only files a table row still names are filed after Create", () => {
    const file = new File(["x"], "id.pdf", { type: "application/pdf" });
    const held = [
      { id: "local-a", docType: "kyc", name: "id.pdf", whatItProves: "", required: false, file },
      { id: "local-b", docType: "kyc", name: "old.pdf", whatItProves: "", required: false, file },
    ];
    const draft: NewConnectDraft = {
      ...emptyDraft(),
      ownerDocuments: held,
      ownerDocDrafts: [{ key: "k", doc_type: "proof_of_identity", card_id: "local-a", name: "id.pdf" }],
    };
    expect(ownerDocumentsToFile(draft).map((doc) => doc.id)).toEqual(["local-a"]);
  });
});

describe("from an approved request: every field arrives filled in", () => {
  const build = {
    id: "con-1",
    connection_no: "CON-26-0101",
    request_no: "SR-26-0101",
    mode: null,
    target_activation: null,
    premises: null,
    prefill: {
      request_id: "req-1",
      request_no: "SR-26-0101",
      applicant_kind: "person",
      applicant_name: "Maria Lopez",
      applicant_email: "maria.lopez@example.com",
      applicant_phone: "(734) 555-0182",
      matched_customer_id: null,
      address_as_given: "143 Willow Bend Dr",
      address_unit_as_given: null,
      plot_or_parcel: null,
      property_type: null,
      what_is_being_built: null,
      units_on_property: null,
      co_applicants: [
        {
          full_name: "Daniel Lopez",
          relationship: "spouse",
          phone: "(734) 555-0144",
          email: "dan.lopez@example.com",
          contact_by: "email",
          date_of_birth: "1986-09-30",
          responsible_for_bills: true,
          ssn_last4: "2208",
          driving_licence_last4: null,
        },
      ],
      contact_by: "text",
      gov_id_last4: "9001",
      paperless: true,
      sms_reminders: true,
    },
  } as unknown as ConnectionDetail;

  it("the cards, Contact by, the government ID and both preferences", () => {
    const draft = draftFromRaisedBuild(emptyDraft(), build);
    expect(draft.owner.contactBy).toBe("text");
    expect(draft.owner.govIdLast4).toBe("9001");
    expect(draft.coOwnersOn).toBe(true);
    expect(draft.coOwners?.[0]).toMatchObject({
      full_name: "Daniel Lopez",
      relationship: "spouse",
      responsible_for_bills: true,
      date_of_birth: "1986-09-30",
      ssn: "",
    });
    expect(draft.communication).toMatchObject({ paperlessBill: true, smsReminders: true });
  });
});

// ══════════════════════════════════════════════════════════════════════════
// ON SCREEN — fill the drawn fields; the draft (and so the commit) holds them
// ══════════════════════════════════════════════════════════════════════════
function mountStep1(over: Partial<NewConnectDraft> = {}) {
  let current: NewConnectDraft = { ...emptyDraft(), ...over };
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(ACCOUNT_CATEGORIES_QUERY_KEY, {
    selectable: [{ code: "residential", name: "Residential" }],
    legacy: [],
  });
  queryClient.setQueryData(ACCOUNT_SUBTYPES_QUERY_KEY, { results: [] });
  queryClient.setQueryData(["lookups", "owner_categories"], {
    results: [{ code: "owner_occupier", name: "Owner-occupier", active: true }],
  });
  const client = createApiClient({
    baseUrl: "",
    tenant: "brazosbend",
    fetchImpl: async () =>
      new Response(JSON.stringify({ count: 0, results: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
  function Host() {
    const [draft, setDraft] = useState<NewConnectDraft>(current);
    current = draft;
    return (
      <OwnerScopeStep
        draft={draft}
        onPatch={(patch) => setDraft((previous) => ({ ...previous, ...patch }))}
        t={t}
        client={client}
      />
    );
  }
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/connections/new?step=1"]}>
          <Routes>
            <Route path="/:tenant/connections/new" element={<Host />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { draft: () => current };
}

const byId = (id: string) => document.getElementById(id) as HTMLInputElement;

describe("image 06 · the owner step's fields reach the commit", () => {
  it("Who, Identity, a co-owner card and the mailing address", () => {
    const host = mountStep1();
    fireEvent.click(screen.getByRole("radio", { name: t("customers.customer.kind.person") }));
    fireEvent.change(byId("full_name"), { target: { value: "Maria Lopez" } });
    fireEvent.change(byId("email"), { target: { value: "maria.lopez@example.com" } });
    fireEvent.change(byId("phone"), { target: { value: "(734) 555-0182" } });
    fireEvent.change(byId("contact_by"), { target: { value: "text" } });
    fireEvent.change(byId("nc_owner_kind"), { target: { value: "owner_occupier" } });
    fireEvent.change(byId("ssn"), { target: { value: "123-45-4471" } });
    fireEvent.change(byId("gov_id_last4"), { target: { value: "9001" } });
    fireEvent.click(screen.getByLabelText(t("customers.moveIn.customer.coOwners.tick")));
    fireEvent.change(byId("co_owner_0_full_name"), { target: { value: "Daniel Lopez" } });
    fireEvent.change(byId("co_owner_0_relationship"), { target: { value: "spouse" } });
    fireEvent.click(screen.getByLabelText(t("customers.account.field.mailingSame")));
    fireEvent.change(byId("mailing_line1"), { target: { value: "PO Box 2210" } });
    fireEvent.change(byId("mailing_city"), { target: { value: "Ypsilanti" } });
    fireEvent.change(byId("mailing_postal_code"), { target: { value: "48197" } });

    const owner = commitPlanOf(host.draft(), null).owner;
    expect(owner).toMatchObject({
      name: "Maria Lopez",
      email: "maria.lopez@example.com",
      phone: "(734) 555-0182",
      kind: "owner_occupier",
      party_kind: "person",
      identity: { ssn: "123-45-4471", phone: "(734) 555-0182" },
      contact_by: "text",
      gov_id_last4: "9001",
      co_owners: [{ full_name: "Daniel Lopez", relationship: "spouse" }],
      addresses: [{ kind: "mailing", line1: "PO Box 2210", city: "Ypsilanti", postal_code: "48197" }],
    });
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-10233 — the charges step draws Move-in's Tax and Discounts panels,
// and the owner block carries them as Move-in's commit does
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CUS-10233 · Move-in's tax exemption and discount claims travel on the owner block", () => {
  const extras = {
    discountsOn: true,
    discounts: [{ key: "d1", discountId: "ds-cap", note: "Card seen" }],
    taxOn: true,
    tax: {
      categoryId: "cat-church",
      certificateRef: "IA-EX-2231",
      issuedOn: "2026-01-15",
      expiresOn: "2027-01-15",
      file: { name: "exemption.pdf", contentType: "application/pdf", base64: "JVBERi0=" },
    },
  };

  it("the certificate block, the claims, and never the blanket exemption", () => {
    const owner = commitPlanOf({ ...emptyDraft(), owner: OWNER, moveInExtras: extras }, null).owner;
    expect(owner).toMatchObject({
      tax_exempt: false,
      tax_exempt_ref: null,
      tax_exempt_expires: null,
      discount_claims: [{ discount_id: "ds-cap", note: "Card seen" }],
      tax_exemption: {
        category_id: "cat-church",
        certificate_ref: "IA-EX-2231",
        issued_on: "2026-01-15",
        expires_on: "2027-01-15",
        certificate: { name: "exemption.pdf", content_type: "application/pdf", content_base64: "JVBERi0=" },
      },
    });
  });

  it("Move-in's own rules hold the step: an exemption needs its type, number, expiry and file", () => {
    const missing = { ...extras, tax: { ...extras.tax, categoryId: "", file: null } };
    expect(moveInExtrasProblems({ ...emptyDraft(), moveInExtras: missing })).toEqual(["tax_category", "tax_file"]);
    expect(moveInExtrasProblems({ ...emptyDraft(), moveInExtras: extras })).toEqual([]);
  });

  it("the charges step mounts Move-in's two panels over the chosen plan's taxes and discounts", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["new-connect", "plan-detail", DRAWN_PLAN_ID, "residential"], {
      detail: DRAWN_DETAIL,
      sections: DRAWN_SECTIONS,
    });
    for (const tax of DRAWN_SECTIONS.taxes) {
      queryClient.setQueryData(["rating", "tax", tax.ref.id, "exemption-categories"], [
        { id: "cat-church", name: "Religious organisation", status: "active" },
      ]);
    }
    let current: NewConnectDraft = { ...emptyDraft(), owner: OWNER, planApartments: DRAWN_PLAN_ID };
    const client = createApiClient({
      baseUrl: "",
      tenant: "brazosbend",
      fetchImpl: async () =>
        new Response(JSON.stringify({ count: 0, results: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    });
    function Host() {
      const [draft, setDraft] = useState<NewConnectDraft>(current);
      current = draft;
      return (
        <ChargesStep
          draft={draft}
          onPatch={(patch) => setDraft((previous) => ({ ...previous, ...patch }))}
          t={t}
          dateFormat="MM/DD/YYYY"
          client={client}
        />
      );
    }
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazosbend/connections/new?step=4"]}>
            <Routes>
              <Route path="/:tenant/connections/new" element={<Host />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByLabelText(t("customers.moveIn.discounts.tick")));
    const discount = document.querySelector('[data-billing-section="discounts"] select') as HTMLSelectElement;
    expect([...discount.options].map((option) => option.textContent)).toContain("CAP / low-income credit");
    fireEvent.change(discount, { target: { value: "ds-cap" } });
    fireEvent.click(screen.getByLabelText(t("customers.moveIn.tax.tick")));
    fireEvent.change(byId("move_in_tax_category"), { target: { value: "cat-church" } });
    fireEvent.change(byId("move_in_tax_ref"), { target: { value: "IA-EX-2231" } });
    expect(document.getElementById("move_in_tax_issued")).not.toBeNull();
    // `DEF-CUS-10263` — Move-in's Tax panel (on both screens) dates with the
    // kit's picker in the utility's format, never the browser's native box.
    for (const id of ["move_in_tax_issued", "move_in_tax_expires"]) {
      expect((document.getElementById(id) as HTMLInputElement).type).not.toBe("date");
    }
    expect(document.getElementById("move_in_tax_certificate")).not.toBeNull();
    expect(current.moveInExtras).toMatchObject({
      discountsOn: true,
      discounts: [{ discountId: "ds-cap" }],
      taxOn: true,
      tax: { categoryId: "cat-church", certificateRef: "IA-EX-2231" },
    });
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-10232 — a co-owner card's summary says what ID is held
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CUS-10232 · the co-owner summary never says No ID over an ID", () => {
  const translate = (key: string, params?: Record<string, unknown>) => t(key, params);

  it("a request's card carries its SSN as a mask, and the mask is never sent", () => {
    const [card] = coOwnersFromRequest([
      {
        full_name: "Daniel Lopez",
        relationship: "spouse",
        phone: "(734) 555-0144",
        email: null,
        contact_by: null,
        date_of_birth: null,
        responsible_for_bills: true,
        ssn_last4: "2208",
        driving_licence_last4: null,
      },
    ]);
    expect(coOwnerSummary("co_owner", card, translate)).toContain("•••-••-2208");
    expect(coOwnerSummary("co_owner", card, translate)).not.toContain(t("customers.moveIn.customer.coOwner.noId"));
    expect(JSON.stringify(coOwnersPayload("co_owner", [card]))).not.toContain("2208");
  });

  it("a typed SSN shows as its last four; a card with nothing still says No ID", () => {
    const typed = { ...emptyCoOwner(), full_name: "Ana Lopez", ssn: "123-45-6789" };
    expect(coOwnerSummary("co_owner", typed, translate)).toContain("•••-••-6789");
    expect(coOwnerSummary("co_owner", typed, translate)).not.toContain("123-45");
    const none = { ...emptyCoOwner(), full_name: "Ana Lopez" };
    expect(coOwnerSummary("co_owner", none, translate)).toContain(t("customers.moveIn.customer.coOwner.noId"));
  });
});
