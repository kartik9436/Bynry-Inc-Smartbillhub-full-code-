// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: `DEF-CUS-9822` (N1 Sub-category) · `DEF-CUS-9823` (N3 one document
//          button) · `DEF-CUS-9824` (N4 Uploaded by) · `DEF-CUS-9825` (N5 View)
//          · `DEF-CUS-9826` (N6 Show/Hide) · `DEF-CUS-9827` (N7 short
//          co-applicant) — the PO's NCT-01 table of 2026-10-06, *"go ahead
//          start it"*.
// Process: 12-governance/22-product-maintenance-process.md §4 — the test that
//          would have caught it, red first on the code that shipped it.
// Rules:   B14 rule 31 · rule 33 · rule 43 · hard-won law 2 (built is not
//          wired) · law 7 (what would make this pass wrongly)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY (law 7):** every case drives the
// mounted step with a stateful host — the draft a clerk's typing produces is
// read back, and the payload is read through `commitPlanOf`, the function the
// press calls. A control that renders and is wired to nothing fails here.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { ACCOUNT_CATEGORIES_QUERY_KEY, ACCOUNT_SUBTYPES_QUERY_KEY } from "./customersShared";
import { commitPlanOf, draftFromRaisedBuild, draftUnits, emptyDraft } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";
import type { ConnectionDetail } from "./newConnectEndpoints";
import { OwnerScopeStep } from "./NewConnectOwnerStep";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string =>
  String(i18next.t(key, params as never));

afterEach(cleanup);
// The content route is built under the tenant in the browser's own address
// (`currentTenant()`), so the page is put at the real path, not only the router.
beforeAll(() => {
  window.history.pushState({}, "", `/${TEST_TENANT}/connections/new`);
});

/** The utility's own sub-types: two under Commercial, one under Residential. */
const SUBTYPES = [
  { id: "st-1", code: "healthcare", name: "Healthcare", parent_code: "commercial", active: true },
  { id: "st-2", code: "retail", name: "Retail", parent_code: "commercial", active: true },
  { id: "st-3", code: "senior", name: "Senior / Low-income", parent_code: "residential", active: true },
  { id: "st-4", code: "closed_one", name: "Closed one", parent_code: "commercial", active: false },
];

function seeded(): QueryClient {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(ACCOUNT_CATEGORIES_QUERY_KEY, {
    selectable: [
      { code: "residential", name: "Residential" },
      { code: "commercial", name: "Commercial" },
    ],
    legacy: [],
  });
  client.setQueryData(ACCOUNT_SUBTYPES_QUERY_KEY, { results: SUBTYPES });
  client.setQueryData(["lookups", "owner_categories"], {
    results: [{ code: "builder", name: "Builder", active: true }],
  });
  client.setQueryData(queryKeys.shellDisplay, { regional: { language: "en" } });
  client.setQueryData(queryKeys.me, {
    id: "u-1",
    full_name: "Dana Ortiz",
    email: "dana@example.test",
    phone: null,
    role: "BILLING_CLERK",
    role_name: "Billing clerk",
    must_change_password: false,
  });
  return client;
}

/** A client whose every read answers an empty list, so nothing reaches a network. */
function quietClient() {
  return createApiClient({
    baseUrl: "",
    tenant: TEST_TENANT,
    // ⊕ lane CF-1 — Move-in's documents table reads a request's own papers.
    fetchImpl: async (input: RequestInfo | URL) =>
      new Response(
        JSON.stringify(
          String(input).includes("/service-requests/req-kyle/documents")
            ? { documents: KYLE_PREFILL.documents }
            : { count: 0, results: [] },
        ),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
  });
}

/** Mount step 1 the way the wizard does — a host holding the draft — and hand
 *  back a reader for the draft the clerk's typing produced. */
function mountStep1(over: Partial<NewConnectDraft> = {}) {
  let current: NewConnectDraft = { ...emptyDraft(), ...over };
  function Host() {
    const [draft, setDraft] = useState<NewConnectDraft>(current);
    current = draft;
    return (
      <OwnerScopeStep
        draft={draft}
        onPatch={(patch) => setDraft((previous) => ({ ...previous, ...patch }))}
        t={t}
        client={quietClient()}
      />
    );
  }
  render(
    <QueryClientProvider client={seeded()}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=1`]}>
          <Routes>
            <Route path="/:tenant/connections/new" element={<Host />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { draft: () => current };
}

function optionWords(select: HTMLElement): string[] {
  return [...(select as HTMLSelectElement).options]
    .filter((option) => option.value !== "")
    .map((option) => option.textContent ?? "");
}

// ══════════════════════════════════════════════════════════════════════════
// N1 · `DEF-CUS-9822` — SUB-CATEGORY IS THE UTILITY'S OWN LIST
// ══════════════════════════════════════════════════════════════════════════
describe("N1 — Sub-category offers the utility's sub-types for the chosen category", () => {
  // ⊕ lane CF-1 (2026-10-18) — the shared Who panel's category pair
  // (`CustomerTypeFields`, Move-in's), ids `account_type` / `account_subtype`.
  it("offers Commercial's active sub-types, never the two hand-typed words", () => {
    mountStep1({ owner: { ...emptyDraft().owner, category: "commercial" } });
    const sub = document.getElementById("account_subtype") as HTMLElement;
    expect(optionWords(sub)).toEqual(["Healthcare", "Retail"]);
    expect(optionWords(sub)).not.toContain("Construction temporary");
  });

  it("changing the category clears a sub-type that does not hang under it, and offers the new list", () => {
    const host = mountStep1({ owner: { ...emptyDraft().owner, category: "commercial" } });
    fireEvent.change(document.getElementById("account_subtype") as HTMLElement, {
      target: { value: "healthcare" },
    });
    expect(host.draft().owner.subCategory).toBe("healthcare");
    fireEvent.change(document.getElementById("account_type") as HTMLElement, {
      target: { value: "residential" },
    });
    expect(host.draft().owner.subCategory).toBe("");
    expect(optionWords(document.getElementById("account_subtype") as HTMLElement)).toEqual([
      "Senior / Low-income",
    ]);
  });

  it("no category chosen: the sub-category is a stated absence, not an empty control", () => {
    mountStep1();
    expect(document.getElementById("account_subtype")).toBeNull();
    expect(document.querySelector("[data-subtype-absent]")?.textContent).toBe(
      t("customers.account.field.subtypeNoneForCategory"),
    );
  });

  // ⊖ *"a draft stored with an old code still reads as its word"* is
  // superseded with the owner's own sub-category select: Move-in's pair offers
  // the utility's list only. The old code is still never SENT (next case).

  it("the chosen sub-type is sent to the account as move-in sends it; an old code is not", () => {
    const owner = { ...emptyDraft().owner, category: "commercial", subCategory: "healthcare" };
    expect(commitPlanOf({ ...emptyDraft(), owner }, null).owner).toMatchObject({
      account_subtype: "healthcare",
    });
    const legacy = { ...owner, subCategory: "permanent" };
    expect(commitPlanOf({ ...emptyDraft(), owner: legacy }, null).owner).not.toHaveProperty(
      "account_subtype",
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════
// N3 · N4 · N5 — THE DOCUMENTS PANEL
// ══════════════════════════════════════════════════════════════════════════
// ⊕ **LANE CF-1 (2026-10-18) — MOVE-IN'S DOCUMENTS TABLE** (drawing set
// `customer-forms-2026-10-18`, image 06). N3's *one Attach a file* and N4's
// *Uploaded by* column belonged to the account uploader this step no longer
// draws; they are superseded by Move-in's table (*+ Add document*, a type and
// an Upload per row). N5 — View opens the browser's own copy — is kept.
function documentsPanel(): HTMLElement {
  const panel = document.querySelector('[data-array="move-in-documents"]');
  expect(panel, "the Documents table is not on step 1").not.toBeNull();
  return panel as HTMLElement;
}

function attach(name: string): void {
  fireEvent.click(screen.getByRole("button", { name: t("customers.moveIn.customer.docs.add") }));
  const selects = documentsPanel().querySelectorAll('[data-cell="doc-type"]');
  fireEvent.change(selects[selects.length - 1] as HTMLElement, {
    target: { value: "proof_of_identity" },
  });
  const inputs = documentsPanel().querySelectorAll('input[type="file"]');
  const file = new File(["%PDF-1.4 photo id"], name, { type: "application/pdf" });
  fireEvent.change(inputs[inputs.length - 1] as HTMLInputElement, { target: { files: [file] } });
}

describe("lane CF-1 — Move-in's documents table holds the file until Create", () => {
  it("+ Add document, a type and Upload hold the file on the draft, in the KYC folder", async () => {
    const host = mountStep1();
    attach("photo-id.pdf");
    await waitFor(() => expect(host.draft().ownerDocuments).toHaveLength(1));
    const held = host.draft().ownerDocuments[0];
    expect(held.docType).toBe("kyc");
    expect(held.name).toBe("photo-id.pdf");
    expect(host.draft().ownerDocDrafts?.[0]).toMatchObject({
      doc_type: "proof_of_identity",
      card_id: held.id,
      name: "photo-id.pdf",
    });
    // B14 rule 31 — the local key is never shown.
    expect(document.body.textContent).not.toContain(held.id);
  });
});

describe("N5 — View opens the attached file", () => {
  it("the file's name opens the draft's own file from an object URL", async () => {
    const opened: string[] = [];
    const original = window.open;
    const created = URL.createObjectURL;
    URL.createObjectURL = () => "blob:nct01-test";
    URL.revokeObjectURL = () => undefined;
    window.open = ((url: string) => {
      opened.push(url);
      return null;
    }) as typeof window.open;
    try {
      mountStep1();
      attach("photo-id.pdf");
      const link = await waitFor(() => {
        const node = documentsPanel().querySelector('[data-doc-file="staged"]');
        if (node === null) throw new Error("no file link on the row");
        return node as HTMLElement;
      });
      fireEvent.click(link);
      expect(opened).toEqual(["blob:nct01-test"]);
    } finally {
      window.open = original;
      URL.createObjectURL = created;
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// N6 · `DEF-CUS-9826` — SHOW / HIDE ON SSN AND LICENCE
// ══════════════════════════════════════════════════════════════════════════
describe("N6 — SSN and Driving licence are masked by default with Show/Hide", () => {
  // ⊕ lane CF-1 — the shared Identity panel's ids.
  for (const id of ["ssn", "driving_licence"]) {
    it(`${id}: masked, Show reveals, Hide masks again; the value typed is unchanged`, () => {
      const host = mountStep1({ owner: { ...emptyDraft().owner, partyKind: "person" } });
      const input = document.getElementById(id) as HTMLInputElement;
      fireEvent.change(input, { target: { value: "123-45-6789" } });
      expect(input.type).toBe("password");
      const toggle = document.querySelector(`[data-reveal="${id}"]`) as HTMLElement;
      expect(toggle, "no Show/Hide beside the box").not.toBeNull();
      expect(toggle.textContent).toBe(t("forms.password.show"));
      fireEvent.click(toggle);
      expect((document.getElementById(id) as HTMLInputElement).type).toBe("text");
      expect(toggle.textContent).toBe(t("forms.password.hide"));
      fireEvent.click(toggle);
      expect((document.getElementById(id) as HTMLInputElement).type).toBe("password");
      const sent = id === "ssn" ? host.draft().owner.ssn : host.draft().owner.drivingLicence;
      expect(sent).toBe("123-45-6789");
    });
  }

  it("the co-owner card's SSN and licence carry Show/Hide too", () => {
    // ⊕ lane CF-1 — the co-applicant is a co-owner CARD now (image 06).
    mountStep1({ coApplicant: { ...emptyDraft().owner, name: "Maya Mark", partyKind: "person" } });
    fireEvent.click(screen.getByRole("button", { name: /Maya Mark/ }));
    expect(document.querySelector('[data-reveal="co_owner_0_ssn"]')).not.toBeNull();
    expect(document.querySelector('[data-reveal="co_owner_0_driving_licence"]')).not.toBeNull();
    expect((document.getElementById("co_owner_0_ssn") as HTMLInputElement).type).toBe("password");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// N2 · `DEF-CUS-9828` — EVERY ANSWER ON THE REQUEST ARRIVES
// ══════════════════════════════════════════════════════════════════════════
/** Kyle Mark's request, as `GET /connections/{id}` serves its `prefill`. */
const KYLE_PREFILL: NonNullable<ConnectionDetail["prefill"]> = {
  request_id: "req-kyle",
  request_no: "SR-26-0412",
  applicant_kind: "person",
  applicant_name: "Kyle Mark",
  applicant_email: "kyle.mark@example.test",
  applicant_phone: "(512) 555-0128",
  matched_customer_id: null,
  address_as_given: "Haustin Towers 2",
  address_unit_as_given: "Apt-12",
  plot_or_parcel: null,
  property_type: null,
  what_is_being_built: null,
  units_on_property: null,
  service_codes: ["water"],
  account_type_code: "residential",
  date_of_birth: "1990-03-14",
  tax_id_last4: null,
  tax_id_present: false,
  address_city_as_given: "Austin",
  address_state_as_given: "TX",
  address_postal_code_as_given: "78701",
  account_subtype_code: "senior",
  mailing_address: { line1: "PO Box 4471", line2: null, city: "Austin", state: "TX", postal_code: "78767" },
  account_custom_data: { name_on_dte_bill: "K. Mark", dte_account_number: "DTE-0091" },
  customer_custom_data: {},
  preferred_language: "es-MX",
  co_applicant: { name: "Maya Mark", email: "maya@example.test", phone: "(512) 555-0129" },
  ssn_last4: "6789",
  driving_licence_last4: "4321",
  documents: [
    {
      id: "doc-photo-id",
      doc_type: "proof_of_identity",
      what_it_proves: null,
      document_number: null,
      name: "kyle-photo-id.pdf",
      size_bytes: 1500,
      original_size_bytes: null,
      uploaded_at: "2026-10-06T14:00:00Z",
      uploaded_by_name: "Kyle Mark",
      file_present: true,
      content_type: "application/pdf",
      required: false,
      verification_state: "verified",
      reject_reason: null,
    },
  ],
};

function kyleBuild(): ConnectionDetail {
  return {
    id: "con-1",
    connection_no: "CON-26-0091",
    request_no: "SR-26-0412",
    mode: null,
    target_activation: null,
    premises: null,
    prefill: KYLE_PREFILL,
  } as unknown as ConnectionDetail;
}

describe("N2 — after Approve, every answer on the request arrives", () => {
  it("carries the address parts, unit, sub-category, mailing, answers, language, co-applicant and documents", () => {
    const draft = draftFromRaisedBuild(emptyDraft(), kyleBuild());
    expect([draft.premise.address, draft.premise.city, draft.premise.state, draft.premise.postalCode]).toEqual([
      "Haustin Towers 2",
      "Austin",
      "TX",
      "78701",
    ]);
    expect(draftUnits(draft).map((unit) => unit.label)).toEqual(["Apt 12"]);
    expect(draft.owner.subCategory).toBe("senior");
    expect(draft.mailing).toMatchObject({ sameAsService: false, address: "PO Box 4471", postalCode: "78767" });
    expect(draft.accountCustomData).toEqual({ name_on_dte_bill: "K. Mark", dte_account_number: "DTE-0091" });
    expect(draft.communication.language).toBe("es-MX");
    expect(draft.coApplicant).toMatchObject({ name: "Maya Mark", phone: "(512) 555-0129", partyKind: "person" });
    expect(draft.requestDocuments?.map((doc) => doc.name)).toEqual(["kyle-photo-id.pdf"]);
    // Never the number — only its last four, and never into the box.
    expect(draft.owner.ssn).toBe("");
    expect(draft.owner.applicationSsnLast4).toBe("6789");
  });

  it("fills only what is EMPTY — the clerk's typing wins", () => {
    const typed = {
      ...emptyDraft(),
      owner: { ...emptyDraft().owner, name: "Kyle J. Mark", phone: "(512) 555-0000" },
      premise: { ...emptyDraft().premise, city: "Round Rock" },
      accountCustomData: { name_on_dte_bill: "Kyle Mark" },
      communication: { ...emptyDraft().communication, language: "en" },
    };
    const draft = draftFromRaisedBuild(typed, kyleBuild());
    expect(draft.owner.name).toBe("Kyle J. Mark");
    expect(draft.owner.phone).toBe("(512) 555-0000");
    expect(draft.owner.email).toBe("kyle.mark@example.test");
    expect(draft.premise.city).toBe("Round Rock");
    expect(draft.accountCustomData).toEqual({ name_on_dte_bill: "Kyle Mark", dte_account_number: "DTE-0091" });
    expect(draft.communication.language).toBe("en");
  });

  it("a matched premises still wins over the applicant's words", () => {
    const build = {
      ...kyleBuild(),
      premises: { id: "p-1", premise_no: "P-0091", name: "Haustin Towers 2", address: "200 Haustin Ave" },
    } as unknown as ConnectionDetail;
    const draft = draftFromRaisedBuild(emptyDraft(), build);
    expect(draft.premise.address).toBe("200 Haustin Ave");
    expect(draft.premise.city).toBe("");
    expect(draftUnits(draft)).toEqual([]);
  });

  it("step 1 lists the request's photo ID as brought in, opens it through the request, and shows ends 6789", async () => {
    const opened: string[] = [];
    const original = window.open;
    window.open = ((url: string) => {
      opened.push(url);
      return null;
    }) as typeof window.open;
    try {
      mountStep1(draftFromRaisedBuild(emptyDraft(), kyleBuild()));
      // ⊕ lane CF-1 — Move-in's table lists the request's papers as locked
      // rows; the SSN on file shows as a mask in its empty box.
      const link = await waitFor(() => {
        const node = documentsPanel().querySelector('[data-doc-file="request"]');
        if (node === null) throw new Error("the request's document is not listed");
        return node as HTMLElement;
      });
      expect(link.textContent).toContain("kyle-photo-id.pdf");
      fireEvent.click(link);
      expect(opened).toHaveLength(1);
      expect(opened[0]).toContain("/service-requests/req-kyle/documents/doc-photo-id/content?as=view");
      expect(document.querySelector('[data-from-request="owner"]')).not.toBeNull();
      expect(document.getElementById("ssn")).toHaveAttribute("placeholder", "•••-••-6789");
    } finally {
      window.open = original;
    }
  });
});

// ══════════════════════════════════════════════════════════════════════════
// N7 · `DEF-CUS-9827` — THE CO-APPLICANT'S SHORT FORM
// ══════════════════════════════════════════════════════════════════════════
// ⊕ **LANE CF-1 (2026-10-18) — N7's short co-applicant form is superseded by
// Move-in's co-owner CARDS** (image 06: *Co-owners · Has co-owners*, one
// folding card per person). What N7 guarded still holds and is asserted: the
// card asks no owner type, category, sub-category or person/company.
describe("N7 — a co-owner card asks only who the person is", () => {
  it("Has co-owners opens a card with the person's fields and nothing of the owner's", () => {
    const host = mountStep1();
    fireEvent.click(screen.getByLabelText(t("customers.moveIn.customer.coOwners.tick")));
    for (const present of [
      "co_owner_0_full_name",
      "co_owner_0_relationship",
      "co_owner_0_phone",
      "co_owner_0_email",
      "co_owner_0_date_of_birth",
      "co_owner_0_ssn",
      "co_owner_0_driving_licence",
    ]) {
      expect(document.getElementById(present), present).not.toBeNull();
    }
    const card = document.querySelector('[data-tick-panel="co_owner"]') as HTMLElement;
    for (const absent of ["nc_owner_kind", "account_type", "account_subtype"]) {
      expect(card.querySelector(`#${absent}`), absent).toBeNull();
    }
    fireEvent.change(document.getElementById("co_owner_0_full_name") as HTMLElement, {
      target: { value: "Maya Mark" },
    });
    expect(host.draft().coOwners?.[0]).toMatchObject({ full_name: "Maya Mark" });
    expect(host.draft().coOwnersOn).toBe(true);
  });
});
