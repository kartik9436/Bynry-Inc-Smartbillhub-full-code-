// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.28–P2.31 + P2.35 (lane MVI-WIZ-BILL) — the
//           move-in's Billing step, images 41–44.
// Rules:    J4 (decision log 2026-10-05): $150.00 + $25.00 + $40.00 =
//           **$215.00**; $100.00 by check → *"$115.00 goes on the first
//           bill."* · OQ-BIL-12788 CLOSED (a) (never taxed at move-in) ·
//           *"FOUR PO RULINGS"* (2) (no System Admin state)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, AND WHAT EACH CASE DOES ABOUT IT:**
//   · a Total typed into the table rather than summed from its rows would
//     read $175.00 and stay there when RUSH is added — so the Total is read
//     before AND after the added row;
//   · a payment line computed from the wrong figure (the plan's total, or the
//     typed amount alone) — so all three of image 41/43/44's sentences are
//     asserted on one table;
//   · a payload that drops a row or keeps the old deposit decision — so the
//     exact body the step adds to Complete is asserted, key by key;
//   · a *Taxable* column or a *held for a System Admin* word sneaking back —
//     both are asserted ABSENT from the whole step.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import type { MoveFeeRow, MoveInPricing } from "@/api/moveInMoneyEndpoints";
import i18n from "@/i18n";

import { emptyCustomerForm, emptyPreferencesForm } from "../NewAccountWizard";
import type { PreferencesForm } from "../NewAccountWizard";
import { billingPayload, billingProblems, emptyStepBillingOwn, onFirstBill } from "./billingModel";
import type { StepBillingOwn } from "./billingModel";
import type { MoveInWizardContext, StepOwn } from "./moveInWizardContext";
import { StepBilling, useStepBillingOwn } from "./StepBilling";

afterEach(cleanup);

const DEPOSIT: MoveFeeRow = {
  kind: "deposit",
  source: "plan",
  code: "DEPOSIT",
  name: "Security deposit",
  amount: "150.0000",
  locked: true,
  refusal: null,
  taxed_at_move_in: false,
};
const CONNECT: MoveFeeRow = {
  kind: "fee",
  source: "plan",
  code: "CONNECT",
  name: "Connection",
  amount: "25.0000",
  priced_by: "flat",
  locked: true,
  refusal: null,
  taxed_at_move_in: false,
};

const PRICING: MoveInPricing = {
  unit_id: "u-1",
  account_type: "residential",
  services: ["water"],
  plan_absent: null,
  plan: {
    as_of: "2026-10-10",
    plan_version: { version: 3, effective_from: "2026-06-01" },
    details: {
      name: "Sample — Residential",
      code: "sample-res",
      customer_classes: [],
      description: null,
      intended_for: { cap_proof: false, min_demand_25kw: false, owner_occupied: false },
      notes: [],
      minimum_bill_display: null,
      budget_billing: false,
    },
    services: [],
    base_total: { amount_display: "20.00", unavailable: null },
    outside_city_surcharge: null,
    charge_codes: [],
    taxes: [],
    combined_tax_rate_display: null,
    deposits: [],
    // DEF-CUS-9779: the plan carries all three; only Low income is claimed —
    // Autopay and Municipal account are the system's to grant.
    discounts: [
      {
        ref: {
          id: "disc-autopay",
          kind: "discount",
          code: "AUTOPAY",
          name: "Autopay",
          version: 1,
          version_label: null,
          effective_from: null,
          effective_to: null,
          next: null,
        },
        value_display: "0.50%",
        gl: null,
        enrolled: 0,
        offered_from: null,
        offered_until: null,
      },
      {
        ref: {
          id: "disc-municipal",
          kind: "discount",
          code: "MUNICIPAL",
          name: "Municipal account",
          version: 1,
          version_label: null,
          effective_from: null,
          effective_to: null,
          next: null,
        },
        value_display: "20.00%",
        gl: null,
        enrolled: 0,
        offered_from: null,
        offered_until: null,
      },
      {
        ref: {
          id: "disc-cap",
          kind: "discount",
          code: "CAP",
          name: "Low income",
          version: 1,
          version_label: null,
          effective_from: null,
          effective_to: null,
          next: null,
        },
        value_display: "25.00%",
        gl: null,
        enrolled: 0,
        offered_from: null,
        offered_until: null,
      },
    ],
    // ⚖️ AMENDED 2026-10-06 (DEF-RAT-9833, PO D2 (b)): Autopay is claimable
    // again and carries `pairs_with`; Municipal account stays out.
    claimable_discounts: [
      {
        ref: {
          id: "disc-autopay",
          kind: "discount",
          code: "AUTOPAY",
          name: "Autopay",
          version: 1,
          version_label: null,
          effective_from: null,
          effective_to: null,
          next: null,
        },
        value_display: "0.50%",
        gl: null,
        enrolled: 0,
        offered_from: null,
        offered_until: null,
        pairs_with: "autopay",
      },
      {
        ref: {
          id: "disc-cap",
          kind: "discount",
          code: "CAP",
          name: "Low income",
          version: 1,
          version_label: null,
          effective_from: null,
          effective_to: null,
          next: null,
        },
        value_display: "25.00%",
        gl: null,
        enrolled: 0,
        offered_from: null,
        offered_until: null,
      },
    ],
    currency: "USD",
  },
  deposit: null,
  fees: { rows: [DEPOSIT, CONNECT], total: "175.0000", currency: "USD" },
  assets: [],
  move_in_fees_taxed: false,
};

/** A client that answers the five reads the step makes, and records each path. */
function client(asked: string[] = []): ApiClient {
  const answer = (path: string, query?: Record<string, string>): unknown => {
    if (path === "/move-ins/pricing") return PRICING;
    if (path === "/move-ins/fees/quote") {
      return {
        kind: "fee",
        source: "charge_code",
        code: query?.code,
        name: "Same-day turn-on",
        amount: "40.0000",
        priced_by: "flat",
        refusal: null,
        taxed_at_move_in: false,
      };
    }
    if (path === "/charges") {
      return { count: 1, next: null, previous: null, results: [{ code: "RUSH", name: "Same-day turn-on" }] };
    }
    if (path === "/payments") return { count: 0, results: [], methods: [{ code: "check", name: "Check" }] };
    if (path === "/shell/display") return { regional: { language: "en-US" } };
    if (path === "/service-requests/categories") {
      return { selectable: [{ code: "residential", name: "Residential" }], legacy: [] };
    }
    return {};
  };
  return {
    get: async (path: string, options?: { query?: Record<string, string> }) => {
      asked.push(path);
      return { status: 200, data: answer(path, options?.query), headers: {} };
    },
  } as unknown as ApiClient;
}

let latest: StepOwn<StepBillingOwn> | null = null;
let latestPrefs: PreferencesForm | null = null;

function Harness(props: { client: ApiClient; tried?: boolean }) {
  const own = useStepBillingOwn();
  latest = own;
  // DEF-RAT-9833 — held, so a test can see a picked discount switch it On.
  const [prefs, setPrefs] = useState<PreferencesForm>(emptyPreferencesForm);
  latestPrefs = prefs;
  const ctx = {
    t: (key: string, params?: Record<string, unknown>) => i18n.t(key, params),
    client: props.client,
    dateFormat: "MM/DD/YYYY",
    timeZone: "America/Chicago",
    standalone: true,
    outgoingUnitId: "u-1",
    ticked: ["water"],
    customer: { ...emptyCustomerForm(), account_type: "residential" },
    preferences: prefs,
    setPreferences: setPrefs,
    currency: "USD",
    tried: { unit: false, customer: false, billing: props.tried === true, review: false },
    markTried: () => undefined,
    own: { billing: own },
  } as unknown as MoveInWizardContext;
  return <StepBilling ctx={ctx} />;
}

function mount(asked: string[] = [], tried = false) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <Harness client={client(asked)} tried={tried} />
    </QueryClientProvider>,
  );
}

function section(name: string): HTMLElement {
  const found = document.querySelector(`[data-billing-section="${name}"]`);
  if (found === null) throw new Error(`no section ${name}`);
  return found as HTMLElement;
}

describe("CR-171-BRC10 P2.28–P2.31 — the move-in's Billing step (images 41–44)", () => {
  it("draws the six panels in the drawn order: Plan, Preferences, Discounts, Tax, Fees, Payment", async () => {
    mount();
    await screen.findByText("Sample — Residential");
    const headings = Array.from(document.querySelectorAll("[data-move-in-billing] > section h3, [data-move-in-billing] > section h2"))
      .map((h) => h.textContent?.trim())
      .filter((text) => text !== "");
    expect(headings.slice(0, 6)).toEqual(["Plan", "Preferences", "Discounts", "Tax", "Fees", "Payment"]);
  });

  it("P2.28: the Plan facts — plan, version on the day, base a month, the deposit rule", async () => {
    mount();
    const facts = await screen.findByText("Sample — Residential");
    const block = facts.closest("dl") as HTMLElement;
    expect(block).toHaveTextContent("Version on 10/10/2026");
    expect(block).toHaveTextContent("v3 · from 06/01/2026");
    expect(block).toHaveTextContent("$20.00 a month");
    expect(block).toHaveTextContent("Residential $150.00");
    expect(screen.getByRole("button", { name: /See full rates/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("P2.30: plan rows are locked, deposit first; the Total foots to the rows; no Taxable column", async () => {
    mount();
    const total = await waitFor(() => {
      const cell = document.querySelector("[data-fees-total]");
      if (cell === null) throw new Error("no total yet");
      return cell as HTMLElement;
    });
    expect(total).toHaveTextContent("$175.00");
    const table = document.querySelector('[data-array="move-in-fees"]') as HTMLElement;
    expect(table).toHaveTextContent("DEPOSIT · Security deposit · Residential");
    expect(table).toHaveTextContent("CONNECT · Connection · Residential");
    expect(within(table).queryByText("Taxable")).toBeNull();
    // A plan row has no ✕ at all (image 41) — *Plan rows stay*.
    expect(within(table).queryAllByRole("button", { name: "Remove fee" })).toHaveLength(0);
    expect(table).toHaveTextContent("Plan rows stay");
  });

  it("P2.30 / J4: + Add fee → RUSH is priced by rating → $215.00", async () => {
    const asked: string[] = [];
    mount(asked);
    await waitFor(() => expect(document.querySelector("[data-fees-total]")).toHaveTextContent("$175.00"));
    fireEvent.click(screen.getByRole("button", { name: "+ Add fee" }));
    const box = await screen.findByPlaceholderText("Type a code or name");
    fireEvent.change(box, { target: { value: "RU" } });
    const option = await screen.findByText("RUSH · Same-day turn-on");
    await act(async () => {
      fireEvent.mouseDown(option);
      fireEvent.click(option);
    });
    await waitFor(() => expect(document.querySelector("[data-fees-total]")).toHaveTextContent("$215.00"));
    expect(asked).toContain("/move-ins/fees/quote");
  });

  it("P2.31 / J4: Pay now $100.00 of $215.00 → '$115.00 goes on the first bill.'; Add to bill → '$215.00 …'", async () => {
    mount();
    await waitFor(() => expect(latest?.value.planRows).not.toBeNull());
    // Whole total untouched → image 41's sentence.
    expect(await screen.findByText("All fees paid now. Receipt prints on complete.")).toBeInTheDocument();
    await act(async () => {
      latest?.set({
        ...(latest as StepOwn<StepBillingOwn>).value,
        added: [
          { key: "f1", code: "RUSH", label: "RUSH · Same-day turn-on", quoted: "40.0000", pricedBy: "flat", refusal: null, typed: "", note: "" },
        ],
      });
    });
    expect(screen.getByText("Fees total $215.00")).toBeInTheDocument();
    fireEvent.change(document.getElementById("move_in_payment_amount") as HTMLElement, { target: { value: "100.00" } });
    expect(await screen.findByText("$115.00 goes on the first bill.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "Add to bill" }));
    expect(await screen.findByText("$215.00 goes on the first bill.")).toBeInTheDocument();
    expect(document.getElementById("move_in_payment_method")).toBeNull();
  });

  it("the ticks open their sections; unticked draws the heading alone (image 44)", async () => {
    mount();
    await screen.findByText("Sample — Residential");
    expect(section("preferences")).toHaveAttribute("data-billing-section-open", "true");
    expect(section("tax")).toHaveAttribute("data-billing-section-open", "false");
    expect(document.getElementById("move_in_tax_category")).toBeNull();
    fireEvent.click(screen.getByLabelText("Tax exempt"));
    expect(document.getElementById("move_in_tax_category")).not.toBeNull();
    expect(document.getElementById("move_in_tax_certificate")).not.toBeNull();
    fireEvent.click(screen.getByLabelText("Claim discounts"));
    const discounts = section("discounts");
    expect(within(discounts).getByRole("combobox", { name: "Discount" })).toBeInTheDocument();
  });

  // ⚖️ AMENDED 2026-10-06 (DEF-RAT-9833) — this read *"offers only Low income,
  // never the automatic discounts"* (DEF-CUS-9779, 2.549.7) until the PO's
  // ruling D2 (b): *"Offer Autopay and Paperless at move-in as drawn"*.
  // Municipal account is still never offered.
  it("DEF-CUS-9779 → DEF-RAT-9833: the claim list offers Autopay and Low income, never Municipal account", async () => {
    mount();
    await screen.findByText("Sample — Residential");
    fireEvent.click(screen.getByLabelText("Claim discounts"));
    const picker = within(section("discounts")).getByRole("combobox", { name: "Discount" });
    const offered = Array.from(picker.querySelectorAll("option"))
      .map((option) => option.textContent ?? "")
      .filter((label) => label !== "" && !/Choose/.test(label));
    expect(offered).toEqual(["Autopay", "Low income"]);
  });

  it("DEF-RAT-9833: picking Autopay switches the Autopay preference On; setting it Off removes the row", async () => {
    mount();
    await screen.findByText("Sample — Residential");
    expect(latestPrefs?.autopay).toBe(false);
    fireEvent.click(screen.getByLabelText("Claim discounts"));
    const picker = within(section("discounts")).getByRole("combobox", { name: "Discount" });
    fireEvent.change(picker, { target: { value: "disc-autopay" } });
    await waitFor(() => expect(latestPrefs?.autopay).toBe(true));
    expect(latest?.value.discounts.map((row) => row.discountId)).toEqual(["disc-autopay"]);
    fireEvent.change(document.getElementById("autopay") as HTMLElement, { target: { value: "off" } });
    await waitFor(() => expect(latest?.value.discounts).toEqual([]));
    expect(latestPrefs?.autopay).toBe(false);
  });

  it("ruling (2): nothing on the step speaks of a System Admin, and no fee says it is taxed", async () => {
    mount();
    await screen.findByText("Sample — Residential");
    fireEvent.click(screen.getByLabelText("Tax exempt"));
    fireEvent.click(screen.getByLabelText("Claim discounts"));
    const text = document.body.textContent ?? "";
    expect(text).not.toMatch(/System Admin|held for|waiting for/i);
    expect(text).not.toMatch(/Taxable/);
  });
});

describe("the body the step adds to Complete (§9.MONEY)", () => {
  const base = (): StepBillingOwn => ({
    ...emptyStepBillingOwn(),
    planRows: [DEPOSIT, CONNECT],
    added: [
      { key: "f1", code: "RUSH", label: "RUSH", quoted: "40.0000", pricedBy: "flat", refusal: null, typed: "", note: "" },
    ],
  });

  it("J4: three rows, the deposit decision, and Pay now $100.00 by check", () => {
    const own: StepBillingOwn = {
      ...base(),
      payment: { mode: "pay_now", methodCode: "check", amount: "100.00", confirmation: "1043", receivedOn: "2026-10-10" },
    };
    expect(onFirstBill(own)).toBe("115.0000");
    expect(billingProblems(own)).toEqual([]);
    expect(billingPayload(own)).toEqual({
      fees: [
        { kind: "deposit", source: "plan", code: "DEPOSIT", amount: "150.0000" },
        { kind: "fee", source: "plan", code: "CONNECT", amount: "25.0000" },
        { kind: "fee", source: "charge_code", code: "RUSH", amount: "40.0000" },
      ],
      deposit: { decision: "required", amount: "150.0000" },
      payment: { mode: "pay_now", method_code: "check", amount: "100.00", confirmation: "1043", received_on: "2026-10-10" },
      tax_exempt: false,
    });
  });

  it("Add to bill sends the mode alone; the whole $215.0000 goes on the first bill", () => {
    const own: StepBillingOwn = { ...base(), payment: { ...base().payment, mode: "add_to_bill" } };
    expect(onFirstBill(own)).toBe("215.0000");
    expect(billingPayload(own).payment).toEqual({ mode: "add_to_bill" });
    expect(billingProblems(own)).toEqual([]);
  });

  it("Pay now holds Continue on no method, no date, and more than the fees", () => {
    const own: StepBillingOwn = { ...base(), payment: { ...base().payment, amount: "300.00" } };
    expect(billingProblems(own)).toEqual(["payment_method", "payment_more", "payment_received"]);
  });

  it("the discount claim and the exemption with its certificate travel as the contract names them", () => {
    const own: StepBillingOwn = {
      ...base(),
      payment: { ...base().payment, mode: "add_to_bill" },
      discountsOn: true,
      discounts: [{ key: "d1", discountId: "disc-cap", note: "" }],
      taxOn: true,
      tax: {
        categoryId: "cat-np",
        certificateRef: "NP-4471",
        issuedOn: "2026-01-15",
        expiresOn: "2029-01-14",
        file: { name: "np-4471-certificate.pdf", contentType: "application/pdf", base64: "JVBERi0=" },
      },
    };
    const body = billingPayload(own);
    expect(body.discount_claims).toEqual([{ discount_id: "disc-cap" }]);
    // DEF-CUS-9724 (PO 2026-10-05): the certificate removes only its own tax,
    // so the account's BLANKET flag and its reference/expiry are never sent.
    expect(body.tax_exempt).toBe(false);
    expect(body).not.toHaveProperty("tax_exempt_ref");
    expect(body).not.toHaveProperty("tax_exempt_expires");
    expect(body.tax_exemption).toEqual({
      category_id: "cat-np",
      certificate_ref: "NP-4471",
      issued_on: "2026-01-15",
      expires_on: "2029-01-14",
      certificate: { name: "np-4471-certificate.pdf", content_type: "application/pdf", content_base64: "JVBERi0=" },
    });
  });

  it("an unpriced added row holds Continue and adds nothing to the Total", () => {
    const own: StepBillingOwn = {
      ...base(),
      added: [{ key: "f2", code: "TAP", label: "TAP", quoted: null, pricedBy: "per_case", refusal: null, typed: "", note: "" }],
      payment: { ...base().payment, mode: "add_to_bill" },
    };
    expect(billingProblems(own)).toEqual(["fee_row"]);
    expect(onFirstBill(own)).toBe("175.0000");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// ⚖️ PO ruling (7), 2026-10-05 — decision log *"A CLERK CAN STILL WAIVE THE
// DEPOSIT"*: *"(a). Clerks use it today, the server already supports it, and the
// fix for 'waived deposit still billed' is already in place."* The deposit row
// carries a Waive row action with a required reason; a waived deposit is sent
// as the server's existing waive (`deposit.decision = "waived"` with its
// `waive_reason`, exactly what the old Deposit step sent), writes no deposit
// line, and the Total and the first-bill line drop by it: $215.00 − $150.00 =
// $65.00.
// ══════════════════════════════════════════════════════════════════════════
describe("ruling (7): Waive on the deposit row", () => {
  const withRush = (): StepBillingOwn => ({
    ...emptyStepBillingOwn(),
    planRows: [DEPOSIT, CONNECT],
    added: [
      { key: "f1", code: "RUSH", label: "RUSH", quoted: "40.0000", pricedBy: "flat", refusal: null, typed: "", note: "" },
    ],
  });

  it("a waived deposit is the server's waive: no deposit row in fees, the reason on the deposit block, $65.00", () => {
    const own: StepBillingOwn = {
      ...withRush(),
      depositWaive: { reason: "Hardship" },
      payment: { mode: "add_to_bill", methodCode: "", amount: "", confirmation: "", receivedOn: "" },
    };
    expect(onFirstBill(own)).toBe("65.0000");
    expect(billingPayload(own)).toEqual({
      fees: [
        { kind: "fee", source: "plan", code: "CONNECT", amount: "25.0000" },
        { kind: "fee", source: "charge_code", code: "RUSH", amount: "40.0000" },
      ],
      deposit: { decision: "waived", amount: "150.0000", waive_reason: "Hardship" },
      payment: { mode: "add_to_bill" },
      tax_exempt: false,
    });
  });

  it("Pay now defaults to the $65.00 left once the deposit is waived", () => {
    const own: StepBillingOwn = {
      ...withRush(),
      depositWaive: { reason: "Hardship" },
      payment: { mode: "pay_now", methodCode: "check", amount: "", confirmation: "", receivedOn: "2026-10-10" },
    };
    expect(onFirstBill(own)).toBe("0.0000");
    expect((billingPayload(own).payment as Record<string, unknown>).amount).toBe("65.0000");
  });

  it("a waive survives a parked draft, reason and all", async () => {
    const { billingHydrate, billingPark } = await import("./billingModel");
    const parked = JSON.parse(JSON.stringify(billingPark({ ...withRush(), depositWaive: { reason: "Hardship" } })));
    expect(billingHydrate(parked).depositWaive).toEqual({ reason: "Hardship" });
    expect(billingHydrate({}).depositWaive).toBeNull();
  });

  it("the row action asks a reason, then the Total and the first-bill line drop by $150.00", async () => {
    mount();
    await waitFor(() => expect(document.querySelector("[data-fees-total]")).toHaveTextContent("$175.00"));
    await act(async () => {
      latest?.set({
        ...(latest as StepOwn<StepBillingOwn>).value,
        added: [
          { key: "f1", code: "RUSH", label: "RUSH · Same-day turn-on", quoted: "40.0000", pricedBy: "flat", refusal: null, typed: "", note: "" },
        ],
      });
    });
    expect(document.querySelector("[data-fees-total]")).toHaveTextContent("$215.00");
    const table = document.querySelector('[data-array="move-in-fees"]') as HTMLElement;
    // Only the deposit row carries it — an icon with its name (B14 rule 15).
    const waive = within(table).getAllByRole("button", { name: "Waive deposit" });
    expect(waive).toHaveLength(1);
    // DEF-CUS-9778: the waive glyph (a struck dollar), never the commit tick —
    // beside $150.00 a tick reads as "paid".
    expect((waive[0] as HTMLElement).querySelector('svg[data-icon="waive"]')).not.toBeNull();
    fireEvent.click(waive[0] as HTMLElement);
    const dialog = await screen.findByRole("dialog");
    // A reason is required: submitting blank keeps the deposit charged.
    await act(async () => {
      fireEvent.click(within(dialog).getByRole("button", { name: "Waive" }));
    });
    expect(latest?.value.depositWaive ?? null).toBeNull();
    fireEvent.change(within(dialog).getByLabelText(/Waive reason/), { target: { value: "Hardship" } });
    await act(async () => {
      fireEvent.click(within(dialog).getByRole("button", { name: "Waive" }));
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(latest?.value.depositWaive).toEqual({ reason: "Hardship" });
    expect(document.querySelector("[data-fees-total]")).toHaveTextContent("$65.00");
    expect(table).toHaveTextContent("Waived");
    expect(table).toHaveTextContent("Hardship");
    fireEvent.click(screen.getByRole("radio", { name: "Add to bill" }));
    expect(await screen.findByText("$65.00 goes on the first bill.")).toBeInTheDocument();
    // Undo puts the $150.00 back.
    fireEvent.click(within(table).getByRole("button", { name: "Undo waive" }));
    await waitFor(() => expect(document.querySelector("[data-fees-total]")).toHaveTextContent("$215.00"));
    expect(latest?.value.depositWaive).toBeNull();
  });
});

