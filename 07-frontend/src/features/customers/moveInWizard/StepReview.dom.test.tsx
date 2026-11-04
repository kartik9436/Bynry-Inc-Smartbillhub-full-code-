// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.32 · P2.33 (lane MVI-WIZ-REV) — step 4 · Review,
//           built from images 45 and 46: Unit / Customer / Billing, each with
//           ✎ Edit, then Messaging.
// Harness:  `StepReview` mounted over a hand-built `MoveInWizardContext` (the
//           seam every step reads) and a fake server, so the OTHER steps'
//           payloads can be set by their contract keys — which is exactly
//           how the step reads them.
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7, habit 2):
//   · **Rows asserted by text alone** would pass with the rows in any order —
//     the LABELS are read in order and compared with the drawing's list.
//   · **A value read from somewhere other than the payload** (a step's
//     internals) would pass while the commit sent something else — the
//     company, owners, fees and payment values are set ONLY through
//     `ctx.own.<step>.payload`, the contract keys.
//   · **An identifier shown whole** would pass a "contains 4567" check — the
//     full Tax ID is typed and the test asserts it is ABSENT.
//
// RED FIRST (law 7): against the tip's `StepReview.tsx` all 8 failed (the old
// one-panel review has no sections). Then three guards broken by hand in the
// new file, each red, each restored: the company block read from nowhere →
// `expected 'None' to be 'Kestrel Bakery'`; the SSN shown whole →
// `expected '123-45-6789' to be '•••-••-6789'`; Customer's ✎ Edit sent to step
// 3 → `expected [ 1, 3, 3 ] to deeply equal [ 1, 2, 3 ]`.
import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import i18n from "@/i18n";
import type { Translator } from "@/features/tenancy/settingsShared";

import { emptyDepositForm } from "../depositCapability";
import { emptyDiscountClaim } from "../moveInRequestBlocks";
import { emptyCustomerForm, emptyPreferencesForm } from "../NewAccountWizard";
import type { MoveInWizardContext, StepOwn } from "./moveInWizardContext";
import { StepReview, maskedLastFour } from "./StepReview";
import type { StepReviewOwn } from "./StepReview";

afterEach(cleanup);

const t: Translator = (key, params) => i18n.t(key, params);

const SERVER: Record<string, unknown> = {
  "/units/u-308/move-in-facts": {
    unit: { id: "u-308", unit_no: "SCW-U-308", label: "Unit 3B", occupancy: "vacant", address: { line1: "8 Quarry Lane", city: "Ottumwa", state: "IA", postal_code: "52501" } },
    building: { premise_no: "P-00063", name: "Kestrel Park ph. 2", routes: [] },
    owner: { name: "Kestrel Holdings", account_no: "AC-2026-00050" },
    history: { first_occupant: true, previous: null, plan_changes: 2 },
  },
  "/units/u-308/move-in-meters": {
    unit_id: "u-308",
    services: [{ service: "water", metered: true, meters: [{ asset_no: "W-5000", kind: "meter", type_name: null, location_note: null, size_class: '5/8"', unit: "kgal", last_read: null, needs_opening_read: true, children: [] }] }],
    unplaced: [],
  },
  "/units/u-308/pricing": {
    unit: { id: "u-308" },
    plan: { id: "p1", code: "SAMPLE-RES", name: "Sample — Residential", version: 3, base_charges: "20.0000" },
    plan_absent: null,
    discounts: { offered: [{ discount_id: "d-auto", code: "AUTOPAY", name: "Autopay 0.50%" }, { discount_id: "d-paper", code: "PAPERLESS", name: "Paperless $1.00" }], granted: null },
  },
  "/customers/cus-231": { id: "cus-231", customer_no: "CU-000231", display_name: "Kestrel Bakery LLC", kind: "company" },
  "/work/raise-options": { types: [{ id: "jt-read", name: "Move-in read" }], priorities: [] },
  "/work/crews": { results: [{ id: "tech-1", kind: "person", name: "R. Patel", slug: "r-patel", role_label: null }] },
  "/service-requests/categories": { selectable: [{ code: "commercial", name: "Commercial" }], legacy: [] },
  "/accounts/subcategories": { results: [{ id: "st-1", code: "small_commercial", name: "Small commercial", parent_code: "commercial" }] },
  "/move-ins/message-templates": { served: true, results: [] },
};

function client(): ApiClient {
  return {
    get: async (path: string) => {
      const bare = path.split("?")[0];
      if (bare === "/move-ins/messages") {
        return {
          status: 200,
          data: { served: true, results: [{ key: "move_in_welcome", channels: ["email"], template: null }, { key: "service_agreement", channels: [], template: null }] },
          headers: {},
        };
      }
      if (bare in SERVER) return { status: 200, data: SERVER[bare], headers: {} };
      throw new Error(`unexpected GET ${path}`);
    },
  } as unknown as ApiClient;
}

function own<T>(value: T, payload: Record<string, unknown> = {}): StepOwn<T> {
  return { value, set: () => undefined, payload, park: {}, hydrate: () => undefined };
}

function ctx(overrides: Partial<MoveInWizardContext> = {}): MoveInWizardContext {
  const customer = {
    ...emptyCustomerForm(),
    full_name: "Kestrel Bakery LLC",
    customer_kind: "company",
    account_type: "commercial",
    account_subtype: "small_commercial",
    email: "nilesh@bynry.io",
    phone: "(732) 630-0285",
    tax_id: "12-3454567",
    mailing_same: true,
  };
  return {
    t,
    client: client(),
    dateFormat: "MM/DD/YYYY",
    timeZone: "America/Chicago",
    standalone: true,
    picker: null,
    unitId: "u-308",
    outgoing: null,
    pickedUnit: null,
    unitLabel: "Kestrel Park ph. 2 · SCW-U-308",
    unitFree: true,
    firstOccupant: true,
    outgoingUnitId: "",
    serviceOffer: ["water", "sewer"],
    ticked: ["water", "sewer"],
    setChosenServices: () => undefined,
    offerLoading: false,
    offerFailed: false,
    openedAt: "2026-10-10",
    setOpenedAt: () => undefined,
    earliest: null,
    dateProblem: null,
    readsDraft: { "a-1": { meterNo: "W-5000", value: "1000", estimate: false, readAt: "" } },
    setReadsDraft: () => undefined,
    fieldVisit: { none: false, rows: [{ key: "r1", type_id: "jt-read", priority_id: "", due_on: "2026-10-10", holder: "technician:tech-1", note: "" }] },
    setFieldVisit: () => undefined,
    customer,
    setCustomer: () => undefined,
    serviceRequestId: "",
    serviceRequestNo: null,
    identityFromRequest: null,
    preferences: emptyPreferencesForm(),
    setPreferences: () => undefined,
    deposit: emptyDepositForm(),
    setDeposit: () => undefined,
    discount: emptyDiscountClaim(),
    setDiscount: () => undefined,
    currency: "USD",
    tried: { unit: false, customer: false, billing: false, review: false },
    markTried: () => undefined,
    goToStep: () => undefined,
    own: {
      unit: own({}),
      customer: own(
        {},
        {
          customer: { customer_id: "cus-231" },
          company: { trading_as: "Kestrel Bakery", business_type: "LLC", registered_in: "Iowa" },
          contact: { full_name: "Nilesh G", job_title: "Owner" },
          co_owners: [{ full_name: "Arun Mehta", ownership_pct: "50", signs_for_company: true }],
          bills_go_to: "contact_person",
        },
      ),
      billing: own(
        {},
        {
          discount_claims: [{ discount_id: "d-auto" }, { discount_id: "d-paper" }],
          fees: [
            { kind: "deposit", source: "plan", code: "DEPOSIT", amount: "150.0000" },
            { kind: "fee", source: "plan", code: "CONNECT", amount: "25.0000" },
            { kind: "fee", source: "charge_code", code: "RUSH", amount: "40.0000" },
          ],
          payment: { mode: "add_to_bill" },
        },
      ),
      review: own<StepReviewOwn>({ extra_messages: [], default_messages: {} }),
    },
    ...overrides,
  } as MoveInWizardContext;
}

function mount(context: MoveInWizardContext) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <StepReview ctx={context} />
    </QueryClientProvider>,
  );
}

function labels(section: string): string[] {
  const block = document.querySelector(`[data-review-section="${section}"]`);
  return Array.from(block?.querySelectorAll("dt") ?? []).map((dt) => dt.textContent ?? "");
}
function value(section: string, id: string): string {
  return (
    document.querySelector(`[data-review-section="${section}"] [data-fact="${id}"] dd`)?.textContent ?? ""
  );
}

describe("DEF-CUS-9762 · the Plan row while its read is in flight", () => {
  it("says it is loading, never None, and then names the plan", async () => {
    let release: () => void = () => undefined;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    const base = client();
    const slow = {
      get: async (path: string) => {
        if (path.split("?")[0] === "/units/u-308/pricing") await held;
        return base.get(path);
      },
    } as unknown as ApiClient;
    mount(ctx({ client: slow }));
    await screen.findByText("Welcome · account opened");
    expect(value("billing", "plan")).not.toBe("None");
    expect(value("billing", "plan")).toBe("Loading…");
    release();
    expect(await screen.findByText("Sample — Residential · v3 · $20.00 a month")).toBeInTheDocument();
  });
});

describe("step 4 · Review (images 45, 46)", () => {
  it("draws Unit, Customer, Billing in that order, each with ✎ Edit, then Messaging", async () => {
    mount(ctx());
    await screen.findByText("Welcome · account opened");
    const sections = Array.from(document.querySelectorAll("[data-review-section]")).map((node) =>
      node.getAttribute("data-review-section"),
    );
    expect(sections).toEqual(["unit", "customer", "billing"]);
    for (const name of ["Unit", "Customer", "Billing"]) {
      expect(screen.getByRole("heading", { name })).toBeInTheDocument();
    }
    expect(screen.getAllByRole("button", { name: "✎ Edit" })).toHaveLength(3);
    expect(screen.getByText("Messaging")).toBeInTheDocument();
  });

  it("the Unit section's rows are image 45's, in its order, with their values", async () => {
    mount(ctx());
    await screen.findByText("Welcome · account opened");
    expect(labels("unit")).toEqual(["Unit", "Address", "Previous", "Services", "Move-in date", "Opening read", "Field visit"]);
    expect(value("unit", "unit")).toBe("Kestrel Park ph. 2 · SCW-U-308");
    expect(await screen.findByText("8 Quarry Lane, Ottumwa, IA 52501")).toBeInTheDocument();
    expect(value("unit", "previous")).toBe("None · first occupant");
    expect(value("unit", "services")).toBe("Water · Sewer");
    // Hard rule 3 — the reading carries its unit.
    expect(await screen.findByText("W-5000 · 1000 kgal")).toBeInTheDocument();
    expect(await screen.findByText("Move-in read · R. Patel · 2026-10-10")).toBeInTheDocument();
  });

  it("the Customer section draws a company's rows from the customer step's PAYLOAD", async () => {
    mount(ctx());
    await screen.findByText("Welcome · account opened");
    expect(labels("customer")).toEqual([
      "Customer ID",
      "Legal name",
      "Trading as",
      "Customer type",
      "Business type",
      "EIN",
      "State of formation",
      "Contact",
      "Owners",
      "Email",
      "Phone",
      "Bills go to",
      "PO on bills",
      "Documents",
      "Mailing address",
    ]);
    expect(await screen.findByText("CU-000231 · existing, linked")).toBeInTheDocument();
    expect(value("customer", "name")).toBe("Kestrel Bakery LLC · Company");
    expect(value("customer", "tradingAs")).toBe("Kestrel Bakery");
    expect(value("customer", "businessType")).toBe("LLC");
    expect(value("customer", "identifier")).toBe("••-•••4567");
    expect(document.body.textContent).not.toContain("12-3454567");
    expect(value("customer", "contact")).toBe("Nilesh G · Owner");
    expect(value("customer", "owners")).toBe("Arun Mehta · 50% · signs");
    expect(value("customer", "billsGoTo")).toBe("The contact person");
    expect(value("customer", "po")).toBe("None");
    expect(value("customer", "documents")).toBe("None");
    expect(value("customer", "mailing")).toBe("Same as service address");
  });

  it("a PERSON draws Full name, SSN and Co-owners, and no company rows", async () => {
    const base = ctx();
    mount({ ...base, customer: { ...base.customer, customer_kind: "person", full_name: "Rosa Pemberton", ssn: "123-45-6789" } });
    await screen.findByText("Welcome · account opened");
    const rows = labels("customer");
    expect(rows).toContain("Full name");
    expect(rows).toContain("SSN");
    expect(rows).toContain("Co-owners");
    for (const companyOnly of ["Trading as", "Business type", "EIN", "State of formation", "Contact", "Bills go to", "PO on bills"]) {
      expect(rows).not.toContain(companyOnly);
    }
    expect(value("customer", "identifier")).toBe("•••-••-6789");
  });

  it("the Billing section: plan, discounts, tax, fees with their exact total, payment, account number", async () => {
    mount(ctx());
    await screen.findByText("Welcome · account opened");
    expect(labels("billing")).toEqual(["Plan", "Preferences", "Discounts", "Tax", "Fees", "Payment", "Account number"]);
    expect(await screen.findByText("Sample — Residential · v3 · $20.00 a month")).toBeInTheDocument();
    expect(value("billing", "preferences")).toBe("Not set");
    expect(value("billing", "discounts")).toBe("Autopay 0.50% · Paperless $1.00");
    // OQ-BIL-12788 (a) — nothing is taxed at move-in; no exemption claimed.
    expect(value("billing", "tax")).toBe("Not exempt");
    expect(value("billing", "fees")).toBe("DEPOSIT $150.00 · CONNECT $25.00 · RUSH $40.00 · total $215.00");
    expect(value("billing", "payment")).toBe("Add to bill · $215.00 on first bill");
    expect(value("billing", "accountNumber")).toBe("Given when you complete");
  });

  it("ruling (7): a waived deposit reads 'Deposit · Waived · <reason>' and is not among the fees", async () => {
    const base = ctx();
    mount({
      ...base,
      own: {
        ...base.own,
        billing: {
          ...base.own.billing,
          payload: {
            fees: [{ kind: "fee", source: "plan", code: "CONNECT", amount: "25.0000" }],
            deposit: { decision: "waived", amount: "150.0000", waive_reason: "Hardship" },
          },
        },
      },
    });
    await screen.findByText("Welcome · account opened");
    expect(labels("billing")).toEqual(["Plan", "Preferences", "Discounts", "Tax", "Fees", "Deposit", "Payment", "Account number"]);
    expect(value("billing", "deposit")).toBe("Waived · Hardship");
    expect(value("billing", "fees")).toBe("CONNECT $25.00 · total $25.00");
  });

  it("Tax reads Exempt when the billing step's payload says tax_exempt (§9.MONEY), whatever the old form holds", async () => {
    const base = ctx();
    mount({ ...base, own: { ...base.own, billing: { ...base.own.billing, payload: { tax_exempt: true } } } });
    await screen.findByText("Welcome · account opened");
    expect(value("billing", "tax")).toBe("Exempt");
  });

  it("✎ Edit opens its own step", async () => {
    const goToStep = vi.fn();
    mount(ctx({ goToStep }));
    await screen.findByText("Welcome · account opened");
    const edits = ["unit", "customer", "billing"].map(
      (id) => document.querySelector(`[data-review-edit="${id}"]`) as HTMLElement,
    );
    edits.forEach((button) => fireEvent.click(button));
    expect(goToStep.mock.calls.map((call) => call[0])).toEqual([1, 2, 3]);
  });

  it("the Messaging table offers the customer step's co-owners and the unit's owner as recipients", async () => {
    let held: StepReviewOwn = { extra_messages: [], default_messages: {} };
    const base = ctx();
    const review: StepOwn<StepReviewOwn> = {
      ...own<StepReviewOwn>(held),
      set: (next) => {
        held = next;
      },
    };
    const view = mount({ ...base, own: { ...base.own, review } });
    await screen.findByText("Welcome · account opened");
    fireEvent.click(screen.getByRole("button", { name: "+ Add message" }));
    view.rerender(
      <QueryClientProvider client={new QueryClient()}>
        <StepReview ctx={{ ...base, own: { ...base.own, review: { ...review, value: held } } }} />
      </QueryClientProvider>,
    );
    const to = within(document.querySelectorAll("[data-editable-row]")[2] as HTMLElement).getAllByRole("combobox")[1];
    expect(within(to).getByRole("option", { name: "Arun Mehta · co-owner" })).toBeInTheDocument();
    expect(await within(to).findByRole("option", { name: "Kestrel Holdings · unit owner" })).toBeInTheDocument();
  });
});

describe("maskedLastFour", () => {
  it("shows the last four only, and nothing for fewer than four digits", () => {
    expect(maskedLastFour("123-45-6789", "ssn")).toBe("•••-••-6789");
    expect(maskedLastFour("12-3454567", "ein")).toBe("••-•••4567");
    expect(maskedLastFour("12", "ein")).toBe("");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// DEF-CUS-10259 · DEF-CUS-10260 — a person's co-owner and a request's papers
// (lane CF-1, found by lane CF-2's walk 2026-10-18)
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CUS-10259 / 10260 · Review reads a co-owner's relationship as words and counts the request's papers", () => {
  function personCtx(): MoveInWizardContext {
    const base = ctx();
    const withDocs = {
      get: async (path: string) => {
        if (path.split("?")[0] === "/service-requests/req-1/documents") {
          return {
            status: 200,
            data: {
              documents: [
                { id: "doc-1", doc_type: "proof_of_identity", name: "maria-id.pdf", file_present: true },
                { id: "doc-2", doc_type: "tenancy_agreement_or_deed", name: "lease.pdf", file_present: true },
                { id: "doc-3", doc_type: "other", name: null, file_present: false },
              ],
            },
            headers: {},
          };
        }
        return base.client.get(path);
      },
    } as unknown as ApiClient;
    return {
      ...base,
      client: withDocs,
      serviceRequestId: "req-1",
      customer: { ...base.customer, customer_kind: "person", full_name: "Maria Lopez", tax_id: "" },
      own: {
        ...base.own,
        customer: own(
          {},
          {
            customer: { display_name: "Maria Lopez", kind: "person" },
            co_owners: [{ full_name: "Daniel Lopez", relationship: "spouse", responsible_for_bills: true }],
            documents: [{ card_id: "card-1", doc_type: "other" }],
          },
        ),
      },
    } as unknown as MoveInWizardContext;
  }

  it("the co-owner reads Spouse, never the code", async () => {
    mount(personCtx());
    await screen.findByText("Welcome · account opened");
    expect(value("customer", "owners")).toBe(`Daniel Lopez · ${t("customers.moveIn.customer.relationship.spouse")}`);
    expect(value("customer", "owners")).not.toContain("spouse");
  });

  it("Documents counts the request's papers with a file beside the clerk's own", async () => {
    mount(personCtx());
    await screen.findByText("Welcome · account opened");
    await vi.waitFor(() =>
      expect(value("customer", "documents")).toBe(t("customers.moveIn.review.documentCount", { count: 3 })),
    );
  });
});
