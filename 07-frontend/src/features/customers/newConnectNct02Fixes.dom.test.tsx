// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  lane NCT-02 (2026-10-06) — DEF-CUS-9830 (PO ruling (a): the
//          co-applicant is saved as a co-owner, only her name required),
//          DEF-CUS-9834 (a portal applicant's file names the applicant),
//          DEF-CUS-9835 (the utility's own state for a request with none),
//          DEF-CUS-9836 (This plan: Taxes and Discounts summaries).
// Tests:   this file
// ───────────────────────────────────────────────────────
/**
 * Each case was run RED on the code that shipped the defect before it was
 * made green.
 *
 * WHAT WOULD MAKE THESE PASS WRONGLY: a co-applicant asserted only on the
 * screen (the panel always rendered) — so the commit payload is read; a State
 * filled from the utility over the applicant's own — so both orders are
 * asserted; a Taxes summary that adds two decimals in the browser — so the
 * figure asserted is the server's `combined_tax_rate_display`, unchanged.
 */
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
import { thisPlanTaxSummary } from "@/features/rating/planSections/ThisPlanBlock";
import { ThisPlanBlock } from "@/features/rating/planSections/ThisPlanBlock";
import { DRAWN_DETAIL, DRAWN_PLAN_ID, DRAWN_SECTIONS } from "@/features/rating/planSections/thisPlanFixture";
import type { PlanSections } from "@/api/planFormEndpoints";

import { ACCOUNT_CATEGORIES_QUERY_KEY, ACCOUNT_SUBTYPES_QUERY_KEY } from "./customersShared";
import { coApplicantShortfall, coOwnersOf, commitPlanOf, draftFromRaisedBuild, emptyDraft } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";
import type { ConnectionDetail } from "./newConnectEndpoints";
import { OwnerScopeStep } from "./NewConnectOwnerStep";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string =>
  String(i18next.t(key, params as never));

afterEach(cleanup);
beforeAll(() => {
  window.history.pushState({}, "", `/${TEST_TENANT}/connections/new`);
});

const maria = (over: Partial<NewConnectDraft["owner"]> = {}) => ({
  ...emptyDraft().owner,
  name: "Maria Mark",
  partyKind: "person",
  ...over,
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-9830 — the co-applicant reaches the server
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CUS-9830 — the co-applicant is sent to be saved as a co-owner", () => {
  it("Maria with only her name travels as one co-owner, every other fact blank", () => {
    const plan = commitPlanOf({ ...emptyDraft(), coApplicant: maria() }, null);
    expect(plan.owner).toMatchObject({
      co_owners: [
        {
          full_name: "Maria Mark",
          email: null,
          phone: null,
          date_of_birth: null,
          ssn: null,
          driving_licence: null,
        },
      ],
    });
  });

  it("what the clerk typed travels, trimmed", () => {
    expect(
      coOwnersOf(maria({ email: " maria@example.test ", ssn: "123-45-6789", dateOfBirth: "1990-04-12" })),
    ).toEqual({
      co_owners: [
        {
          full_name: "Maria Mark",
          email: "maria@example.test",
          phone: null,
          date_of_birth: "1990-04-12",
          ssn: "123-45-6789",
          driving_licence: null,
        },
      ],
    });
  });

  it("no co-applicant, no co-owner on the payload", () => {
    expect(commitPlanOf(emptyDraft(), null).owner).not.toHaveProperty("co_owners");
  });

  it("only her name is required; an email is checked only when given", () => {
    expect(coApplicantShortfall(null)).toBeNull();
    expect(coApplicantShortfall(maria())).toBeNull();
    expect(coApplicantShortfall(maria({ name: "  " }))).toBe(
      "customers.newConnect.step1.coApplicantNameRequired",
    );
    expect(coApplicantShortfall(maria({ email: "maria-at-example" }))).toBe("customers.contact.email_format");
    expect(t("customers.newConnect.step1.coApplicantNameRequired")).toBe("Enter the co-applicant's name.");
  });

  it("a request's co-applicant, prefilled, is sent the same way", () => {
    const draft = draftFromRaisedBuild(emptyDraft(), build({}));
    expect(commitPlanOf(draft, null).owner).toMatchObject({
      co_owners: [{ full_name: "Maya Mark", email: "maya@example.test", phone: "(512) 555-0129" }],
    });
  });

  it("the co-owner card draws no asterisk but on Full name", () => {
    // ⊕ lane CF-1 — the co-applicant is Move-in's co-owner CARD (image 06).
    mountStep1({ coApplicant: maria() });
    fireEvent.click(screen.getByRole("button", { name: /Maria Mark/ }));
    const form = document.querySelector('[data-tick-panel="co_owner"]') as HTMLElement;
    expect(form).not.toBeNull();
    const required = [...form.querySelectorAll("input[required], input[aria-required='true']")].map(
      (input) => input.id,
    );
    expect(required).toEqual(["co_owner_0_full_name"]);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-9835 — State for a portal request
// ══════════════════════════════════════════════════════════════════════════
function build(over: Partial<NonNullable<ConnectionDetail["prefill"]>>): ConnectionDetail {
  return {
    id: "con-1",
    connection_no: "CON-26-0091",
    request_no: "SR-26-0412",
    mode: null,
    target_activation: null,
    premises: null,
    prefill: {
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
      date_of_birth: null,
      tax_id_last4: null,
      tax_id_present: false,
      address_city_as_given: "Austin",
      address_state_as_given: null,
      address_postal_code_as_given: "78701",
      utility_state: "TX",
      co_applicant: { name: "Maya Mark", email: "maya@example.test", phone: "(512) 555-0129" },
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
          uploaded_by_role: "applicant",
          file_present: true,
          content_type: "application/pdf",
          required: false,
          verification_state: "not_checked",
          reject_reason: null,
        },
      ],
      ...over,
    },
  } as unknown as ConnectionDetail;
}

describe("DEF-CUS-9835 — State is the utility's own when the request gives none", () => {
  it("a portal request with no state fills State with TX", () => {
    expect(draftFromRaisedBuild(emptyDraft(), build({})).premise.state).toBe("TX");
  });

  it("the applicant's own state wins over the utility's", () => {
    expect(draftFromRaisedBuild(emptyDraft(), build({ address_state_as_given: "OK" })).premise.state).toBe("OK");
  });

  it("a State the clerk typed is never overwritten", () => {
    const typed = { ...emptyDraft(), premise: { ...emptyDraft().premise, state: "NM" } };
    expect(draftFromRaisedBuild(typed, build({})).premise.state).toBe("NM");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-9834 — the applicant's photo ID names the applicant
// ══════════════════════════════════════════════════════════════════════════
function seeded(): QueryClient {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(ACCOUNT_CATEGORIES_QUERY_KEY, {
    selectable: [{ code: "residential", name: "Residential" }],
    legacy: [],
  });
  client.setQueryData(ACCOUNT_SUBTYPES_QUERY_KEY, { results: [] });
  client.setQueryData(["lookups", "owner_categories"], { results: [] });
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

function quietClient() {
  return createApiClient({
    baseUrl: "",
    tenant: TEST_TENANT,
    // ⊕ lane CF-1 — Move-in's documents table reads a request's own papers.
    fetchImpl: async (input: RequestInfo | URL) =>
      new Response(
        JSON.stringify(
          String(input).includes("/service-requests/req-kyle/documents")
            ? { documents: build({}).prefill?.documents ?? [] }
            : { count: 0, results: [] },
        ),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
  });
}

function mountStep1(over: Partial<NewConnectDraft> = {}) {
  const start: NewConnectDraft = { ...emptyDraft(), ...over };
  function Host() {
    const [draft, setDraft] = useState<NewConnectDraft>(start);
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
}

describe("DEF-CUS-9834 — Uploaded by names the applicant for a portal file", () => {
  // ⊕ lane CF-1 (2026-10-18) — the step draws Move-in's documents table
  // (image 06), which has no *Uploaded by* column: the request's paper is a
  // locked row named by its TYPE. The uploader's name stays on the request's
  // own Documents tab, where DEF-CUS-9834 is still served.
  it("the request's photo ID is a locked row reading Proof of identity", async () => {
    mountStep1(draftFromRaisedBuild(emptyDraft(), build({})));
    const panel = await waitFor(() => {
      const node = document.querySelector('[data-array="move-in-documents"]');
      if (node === null || !(node.textContent ?? "").includes("kyle-photo-id.pdf")) {
        throw new Error("the request's paper is not listed");
      }
      return node as HTMLElement;
    });
    expect(panel.textContent).toContain(t("customers.serviceRequest.docType.proof_of_identity"));
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-9836 — This plan: Taxes and Discounts summaries
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CUS-9836 — the Taxes and Discounts summaries read as drawn", () => {
  it("Taxes: the count and the server's total for this class", () => {
    expect(thisPlanTaxSummary(DRAWN_SECTIONS, t)).toBe("2 · 8.00% total");
  });

  it("a flat tax is named beside the total, never added to it", () => {
    const flat = {
      ...DRAWN_SECTIONS,
      taxes: [
        ...DRAWN_SECTIONS.taxes,
        { ...DRAWN_SECTIONS.taxes[0], rate_percent: null, rate_display: "$2.00" },
      ],
    } as PlanSections;
    expect(thisPlanTaxSummary(flat, t)).toBe("3 · 8.00% total · 1 flat");
  });

  it("no single figure: the count alone", () => {
    expect(thisPlanTaxSummary({ ...DRAWN_SECTIONS, combined_tax_rate_display: null }, t)).toBe("2");
  });

  it("Discounts summarise by name, never the code in capitals", () => {
    render(
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=2`]}>
        <Routes>
          <Route
            path="/:tenant/connections/new"
            element={
              <ThisPlanBlock
                planId={DRAWN_PLAN_ID}
                detail={DRAWN_DETAIL}
                sections={DRAWN_SECTIONS}
                services={["battery", "solar"]}
                className="Residential"
                t={t}
              />
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    const summary = [...document.querySelectorAll("button")]
      .map((button) => button.textContent ?? "")
      .find((text) => text.startsWith("Discounts"));
    expect(summary).toBeDefined();
    expect(summary).toContain("CAP / low-income credit");
    expect(summary).toContain("Autopay");
    expect(summary).not.toMatch(/\bAUTOPAY\b|\bCAP \d/);
  });
});
