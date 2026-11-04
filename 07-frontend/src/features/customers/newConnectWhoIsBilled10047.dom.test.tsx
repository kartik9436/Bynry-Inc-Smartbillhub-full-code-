// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CUS-10047 — step 4 *Who is billed* always read *"Master account
//          · John doe"*, though the owner's account is a REGULAR one on a
//          single-family type · DEF-CUS-10048 — *"No master account to bill.
//          Remove the charges."* refused Continue after the clerk waited on
//          the screen, and named *master* whatever was actually missing.
// PO, 2026-10-11: accounts and payment are created at submission, so a charge
//          must never be refused for want of an account the submission
//          itself creates.
// ───────────────────────────────────────────────────────
//
// WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2):
// * Asserting the refusal from a draft built by hand only. The timing case
//   mounts the real wizard under its route, on a build carrying SR-26-0027,
//   and reads the payer option the clerk sees — enabled, and named — before
//   and after the background event.
// * A refetch that answers the SAME data proves nothing about an overwrite.
//   The build refetch below answers a DIFFERENT phone, so a re-hydrate would
//   show; the types case empties the cache entry under the mounted wizard.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { NewConnectWizard } from "./NewConnectWizard";
import { emptyDraft, noOneToBillReason, ownerAccountKind } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";
import { newConnectPremisesTypesQueryKey } from "./NewConnectPremiseStep";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const t = (key: string) => String(i18next.t(key));

/** John doe's single-family home, one unit, one charge on step 4. */
function john(over: Partial<NewConnectDraft> = {}): NewConnectDraft {
  const blank = emptyDraft();
  return {
    ...blank,
    owner: { ...blank.owner, name: "John doe" },
    premise: { ...blank.premise, address: "12 Elm Street", premiseType: "single_family", accountKind: "regular" },
    pattern: { prefix: "", from: "2", to: "2", includeCommonArea: false },
    quoteLines: [{ chargeCode: "CONN", basis: "per meter" }],
    quoteDueDays: "30",
    ...over,
  };
}

describe("DEF-CUS-10047 · the payer names the owner's account the build opens", () => {
  it("a single-family home is a Regular account; an apartment type a Master one", () => {
    expect(ownerAccountKind(john())).toBe("regular");
    expect(ownerAccountKind(john({ premise: { ...john().premise, premiseType: "apartment", accountKind: "master" } }))).toBe("master");
  });

  it("a single-family type that opens none still says Regular, never Master", () => {
    const two = john({ pattern: { prefix: "", from: "1", to: "2", includeCommonArea: false } });
    expect(ownerAccountKind(two)).toBe("regular");
  });
});

describe("DEF-CUS-10048 · the refusal names what is actually missing", () => {
  it("a build that opens the owner's account is never refused", () => {
    expect(noOneToBillReason(john())).toBeNull();
    // ...and a master type opens it too, with one unit typed (CR-162-BRC10 Q1).
    expect(noOneToBillReason(john({ premise: { ...john().premise, accountKind: "master" } }))).toBeNull();
  });

  it("no charge, no refusal", () => {
    expect(noOneToBillReason(john({ quoteLines: [], owner: emptyDraft().owner }))).toBeNull();
  });

  it("each cause names its own fix, and none says master over a regular home", () => {
    const blankOwner = john({ owner: emptyDraft().owner });
    expect(noOneToBillReason(blankOwner)).toBe("customers.newConnect.step6.nameOwnerToBill");
    const noType = john({ premise: { ...john().premise, premiseType: "", accountKind: "" } });
    expect(noOneToBillReason(noType)).toBe("customers.newConnect.step6.typeToBill");
    const twoHomes = john({ pattern: { prefix: "", from: "1", to: "2", includeCommonArea: false } });
    expect(noOneToBillReason(twoHomes)).toBe("customers.newConnect.step6.oneHomeToBill");
    const onFile = john({ premise: { ...john().premise, premisesId: "p-on-file" } });
    expect(noOneToBillReason(onFile)).toBe("customers.newConnect.step6.noRegularToBill");
    const unanswered = john({ premise: { ...john().premise, accountKind: "" } });
    expect(noOneToBillReason(unanswered)).toBe("customers.newConnect.step6.noMasterToBill");
    expect(t("customers.newConnect.step6.oneHomeToBill")).toBe("Regular account takes one unit. Fix step 3.");
  });

  it("the owner type is not a cause: an unchosen owner type still bills", () => {
    expect(john().owner.kind).toBe("");
    expect(noOneToBillReason(john())).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════
// THE WIZARD, MOUNTED — a background event must not undo the clerk's work
// ════════════════════════════════════════════════════════════════════════

const BUILD_ID = "01a0b111-2222-7333-8444-555566660048";

function build(phone: string) {
  return {
    id: BUILD_ID,
    connection_no: "CON-26-0248",
    state: "draft",
    premises: null,
    prefill: {
      request_id: "r-48",
      request_no: "SR-26-0027",
      applicant_kind: "person",
      applicant_name: "John doe",
      applicant_email: "john.doe@example.test",
      applicant_phone: phone,
      matched_customer_id: null,
      address_as_given: "12 Elm Street",
      address_unit_as_given: "2",
      plot_or_parcel: null,
      property_type: "single_family",
      what_is_being_built: null,
      units_on_property: 2,
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
  };
}

const TYPES = [{ code: "single_family", name: "Single family", active: true, account_kind: "regular" }];

function mountWizard(step: number) {
  let phone = "+6857736865";
  const answer = (url: string) => {
    const body = url.includes(`/connections/${BUILD_ID}`)
      ? build(phone)
      : url.includes("/premises/types")
        ? TYPES
        : { count: 0, results: [] };
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };
  // The wizard reads the types through the app's own client; while a reset
  // is in flight that read has not answered yet.
  vi.stubGlobal("fetch", () => new Promise<Response>(() => undefined));
  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL) => answer(String(input)),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(newConnectPremisesTypesQueryKey, TYPES);
  window.history.pushState({}, "", "/brazosbend/connections/new");
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/brazosbend/connections/new?step=${step}&build=${BUILD_ID}`]}>
          <Routes>
            <Route path="/:tenant/connections/new" element={<NewConnectWizard client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return {
    queryClient,
    changePhoneOnServer: (next: string) => {
      phone = next;
    },
  };
}

function payerOption(): HTMLOptionElement {
  return (document.getElementById("nc_quote_payer") as HTMLSelectElement).querySelector(
    'option[value="owner_account"]',
  ) as HTMLOptionElement;
}

describe("DEF-CUS-10048 · nothing in the background overwrites the draft", () => {
  it("step 4 names the Regular account and offers it, before and after the types read is emptied", async () => {
    const { queryClient } = mountWizard(4);
    await waitFor(() => expect(payerOption().textContent).toBe("Regular account · John doe"));
    expect(payerOption()).not.toBeDisabled();
    // The cache entry the account kind is copied from is emptied under the
    // mounted wizard (a reset; the re-read has not answered). Before the fix
    // the copy wrote "" over `regular`: the option went disabled, read
    // *Master account*, and Continue refused the charges.
    await act(async () => {
      void queryClient.resetQueries({ queryKey: newConnectPremisesTypesQueryKey });
      await new Promise((resolve) => setTimeout(resolve, 50));
    });
    expect(payerOption().textContent).toBe("Regular account · John doe");
    expect(payerOption()).not.toBeDisabled();
  });

  it("a refetched build never re-fills over what the clerk typed", async () => {
    const { queryClient, changePhoneOnServer } = mountWizard(1);
    // ⊕ lane CF-1 — the shared customer form's id.
    const phone = () => document.getElementById("phone") as HTMLInputElement;
    await waitFor(() => expect(phone().value).toBe("+6857736865"));
    fireEvent.change(phone(), { target: { value: "(512) 555-0100" } });
    changePhoneOnServer("+10000000000");
    await act(async () => {
      await queryClient.refetchQueries({ queryKey: ["new-connect-draft", BUILD_ID] });
    });
    expect(phone().value).toBe("(512) 555-0100");
  });
});
