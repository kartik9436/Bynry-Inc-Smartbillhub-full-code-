// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CUS-10044 (step 1: the browser filled the clerk's saved login;
//          the request's phone and owner type were not carried) ·
//          DEF-CUS-10045 (step 2: Unit, apt. or suite, City, State and ZIP
//          empty though SR-26-0027 carries them)
// Ruling:  PO 2026-10-11, verbatim: *"we need to auto fill this information
//          from service request if provided, if not provided keep them empty
//          - that is what we need to do"*.
// Rules:   BR-CUS-092(c) (SSN and licence are last four only on a request,
//          never copied into the box) · hard rule 8 (an address lives on the
//          premises; a matched premises' town is the register's)
// ───────────────────────────────────────────────────────
//
// WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2):
// * Reading component state. There is none to read; the wizard cases assert
//   the VALUE IN THE INPUT a clerk sees, mounted under the real route.
// * A prefill that GUESSES. "Keep them empty" is half the ruling, so the owner
//   type — which a request does not capture — is asserted EMPTY, and so are
//   the SSN and licence boxes, which the request holds as last four only.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { NewConnectWizard } from "./NewConnectWizard";
import { draftFromRaisedBuild, emptyDraft } from "./newConnectDraft";
import type { ConnectionDetail } from "./newConnectEndpoints";

afterEach(cleanup);

const BUILD_ID = "01a0b111-2222-7333-8444-555566660027";

/** SR-26-0027, John doe, as the PO's screenshots show it. */
const SR_0027 = {
  id: BUILD_ID,
  connection_no: "CON-26-0227",
  state: "draft",
  premises: null,
  prefill: {
    request_id: "01a0e111-2222-7333-8444-000011110027",
    request_no: "SR-26-0027",
    applicant_kind: "person",
    applicant_name: "John doe",
    applicant_email: "john.doe@example.test",
    applicant_phone: "+6857736865",
    matched_customer_id: null,
    address_as_given: "12 Elm Street",
    address_unit_as_given: "2",
    address_city_as_given: "Austin",
    address_state_as_given: "TX",
    address_postal_code_as_given: "78704",
    plot_or_parcel: null,
    property_type: "single_family",
    what_is_being_built: null,
    units_on_property: 2,
    service_codes: ["water"],
    account_type_code: "residential",
    account_subtype_code: "senior",
    date_of_birth: "1980-04-02",
    preferred_language: "es",
    ssn_last4: "6789",
    driving_licence_last4: "4321",
  },
  unit_summary: null,
  applicant: "John doe",
  request_no: "SR-26-0027",
  mode: "our_crew",
  started_at: null,
  target_activation: null,
  waiting_on: null,
  units: 0,
  orders: { done: 0, total: 0 },
  services: [],
  work_orders: [],
  unit_rows: [],
  assets: [],
  unavailable: [],
} as unknown as ConnectionDetail;

function mountWizard(step: number) {
  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL) => {
      const body = String(input).includes(`/connections/${BUILD_ID}`)
        ? SR_0027
        : { count: 0, results: [] };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  window.history.pushState({}, "", "/brazosbend/connections/new");
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/brazosbend/connections/new?step=${step}&build=${BUILD_ID}`]}>
          <Routes>
            <Route path="/:tenant/connections/new" element={<NewConnectWizard client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function input(id: string): HTMLInputElement {
  return document.getElementById(id) as HTMLInputElement;
}

describe("DEF-CUS-10044 · step 1 carries every answer the request holds", () => {
  it("the draft takes phone, email, name, DOB, class, sub-type, kind and language", () => {
    const draft = draftFromRaisedBuild(emptyDraft(), SR_0027);
    expect(draft.owner.phone).toBe("+6857736865");
    expect(draft.owner.email).toBe("john.doe@example.test");
    expect(draft.owner.name).toBe("John doe");
    expect(draft.owner.dateOfBirth).toBe("1980-04-02");
    expect(draft.owner.category).toBe("residential");
    expect(draft.owner.subCategory).toBe("senior");
    expect(draft.owner.partyKind).toBe("person");
    expect(draft.communication.language).toBe("es");
  });

  it("what the request does not hold stays EMPTY — owner type, SSN, licence", () => {
    const draft = draftFromRaisedBuild(emptyDraft(), SR_0027);
    // A request captures no owner type; the ruling is "keep them empty".
    expect(draft.owner.kind).toBe("");
    // BR-CUS-092(c) — last four only, shown as help, never copied.
    expect(draft.owner.ssn).toBe("");
    expect(draft.owner.drivingLicence).toBe("");
    expect(draft.owner.applicationSsnLast4).toBe("6789");
    expect(draft.owner.applicationLicenceLast4).toBe("4321");
  });

  it("on screen: Phone holds the request's number and asks the browser for a phone", async () => {
    mountWizard(1);
    // ⊕ lane CF-1 — the shared customer form's ids (image 06).
    await waitFor(() => expect(input("phone").value).toBe("+6857736865"));
    expect(input("email").value).toBe("john.doe@example.test");
    expect(input("phone")).toHaveAttribute("autocomplete", "tel");
    expect(input("email")).toHaveAttribute("autocomplete", "email");
    // The two masked boxes are never a saved login.
    expect(input("ssn")).toHaveAttribute("autocomplete", "new-password");
    expect(input("driving_licence")).toHaveAttribute("autocomplete", "new-password");
    expect(input("ssn").value).toBe("");
  });
});

describe("DEF-CUS-10045 · step 2 carries the request's unit, city, state and ZIP", () => {
  it("the draft takes the applicant's unit line and town, state and ZIP", () => {
    const draft = draftFromRaisedBuild(emptyDraft(), SR_0027);
    expect(draft.premise.unit).toBe("2");
    expect(draft.premise.city).toBe("Austin");
    expect(draft.premise.state).toBe("TX");
    expect(draft.premise.postalCode).toBe("78704");
  });

  it("over a MATCHED premises the town, state and ZIP are the register's", () => {
    const matched = {
      ...SR_0027,
      premises: {
        id: "01a0c888-9999-7aaa-8bbb-ccccddddeeee",
        premise_no: "P-00074",
        name: "Elm House",
        address: "12 Elm Street",
        city: "Round Rock",
        state: "TX",
        postal_code: "78664",
      },
    } as unknown as ConnectionDetail;
    const draft = draftFromRaisedBuild(emptyDraft(), matched);
    expect(draft.premise.city).toBe("Round Rock");
    expect(draft.premise.postalCode).toBe("78664");
  });

  it("a request with no unit line and no town leaves those boxes EMPTY", () => {
    const bare = {
      ...SR_0027,
      prefill: {
        ...SR_0027.prefill,
        address_unit_as_given: null,
        address_city_as_given: null,
        address_postal_code_as_given: null,
      },
    } as unknown as ConnectionDetail;
    const draft = draftFromRaisedBuild(emptyDraft(), bare);
    expect(draft.premise.unit).toBe("");
    expect(draft.premise.city).toBe("");
    expect(draft.premise.postalCode).toBe("");
  });

  it("a clerk's own typing is never replaced by the request", () => {
    const typed = emptyDraft();
    const draft = draftFromRaisedBuild(
      { ...typed, premise: { ...typed.premise, unit: "Suite 9", city: "Dallas" } },
      SR_0027,
    );
    expect(draft.premise.unit).toBe("Suite 9");
    expect(draft.premise.city).toBe("Dallas");
  });

  it("on screen: step 2 shows unit 2, Austin, TX and 78704", async () => {
    mountWizard(2);
    await waitFor(() => expect(input("nc_unit").value).toBe("2"));
    expect(input("nc_city").value).toBe("Austin");
    expect(input("nc_state").value).toBe("TX");
    expect(input("nc_zip").value).toBe("78704");
  });
});
