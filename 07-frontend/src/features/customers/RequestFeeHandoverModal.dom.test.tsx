// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-6376 — *Record what was handed over* on a service request
//          is Record a payment's form, fixed to the application fee. PO, on
//          SR-26-0016, verbatim: *"this screens takes the payment it should be
//          similar to record payment form so pasting date, type of payment ,
//          memo and it will take only application fee"*.
//          DEF-CUS-6374 — the till rule at this door.
// Rules:   B14 rules 33, 38, 43 · CLAUDE.md hard rule 2 · BR-TEN-081 ·
//          BR-PAY-026 · PO 2026-09-23 §3.4 · decision log 2026-09-19 (A2)
// Tests:   this file
// ───────────────────────────────────────────────────────
//
// ⚠ **MOUNTED THROUGH THE PAGE, UNDER THE REAL PATH PATTERN**
// (`/:tenant/requests/:requestId`, `App.tsx`'s own), and opened by the Fees
// block's own button — so what is asserted is the modal a clerk reaches, not
// the component in isolation. `useParams()` then gives the page its request
// id, and the POST this file inspects is addressed by it.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (hard-won law 7, habit 2), and what
// each case does about it:
//   * *a posting date is posted* passes on a field posting today no matter
//     what is typed — so a DIFFERENT day is typed and that day is asserted;
//   * *the method list is served* passes on a hand-typed list that happens to
//     include `check` — so `money_order` (never in the old three) is asserted
//     present and `cheque` (only in the old three) absent;
//   * *the purpose is fixed* passes on a select that defaults to the fee — so
//     the control is asserted to be a read-only INPUT and the body to carry no
//     `purpose` at all.
//
// ⚠ **EVERY CASE WAS RUN RED AT THIS LANE'S STARTING TIP** (`c99bc40ff`, in a
// separate `git worktree`, under this same vitest) before the build; what each
// found there is quoted on the case.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";
import type { CounterRow } from "@/api/counterEndpoints";
import { queryKeys } from "@/api/queryClient";
import { myOpenCounterQueryKey } from "@/features/payments/counterQueries";

import { withTheFeeFormatted } from "./RequestFeeHandoverModal";
import { ServiceRequestDetailPage } from "./ServiceRequestDetailPage";

const REQUEST_ID = "01a09540-7900-7dfa-abf4-b30b3c0fb6b8";
const FEE_ID = "0199a1d2-7c4e-7a10-9f31-2b6c5d4e8a02";
const ME = "M. Vega";

const DETAIL = {
  header: {
    id: REQUEST_ID,
    request_no: "SR-26-0071",
    number_absence: null,
    state: "submitted",
    classification: "new_connection",
    applicant: "Okonkwo, Adaeze",
    address_as_given: "88 Pine Vista · Unit 2",
    lookup_found: null,
    received_at: "2026-08-14T09:22:00Z",
    received_by: null,
    channel: "walk_in",
    waiting_on: "documents",
    waiting_since: "2026-08-14T09:22:00Z",
    requested_start: null,
  },
  actions: {
    // ⚠ **WHAT THE STATE ALLOWS, WHICH IS WHAT THE HEAD'S FOUR BUTTONS READ.**
    // `available: []` here would leave every one of them disabled and the
    // assertions below would pass over a screen with four dead controls —
    // hard-won law 2's mirror, in a fixture.
    available: ["approve", "refuse", "request_info", "withdraw"],
    can_approve: false,
    approve_blocked_by: ["documents_verified"],
    can_park: true,
  },
  applicant: {
    name: "Okonkwo, Adaeze",
    phone: null,
    email: null,
    language: null,
    person_or_company: null,
    co_applicant: { name: null, email: null, phone: null },
    // An applicant who gave neither identifier and no date of birth: nothing
    // here may draw the "stored encrypted" claim over a blank (BR-CUS-092(d)).
    identifier: {
      ssn_present: false,
      ssn_last4: null,
      stored_encrypted: false,
      drivers_licence_last4: null,
      drivers_licence_present: false,
      drivers_licence_stored_encrypted: false,
    },
    date_of_birth: null,
    acting_for_absence: { tracks: "DEF-638" },
    customer_match: {
      customer_id: null,
      tier: null,
      basis: null,
      confirmed_at: null,
      may_move_money: false,
    },
  },
  location_and_services: {
    address_as_given: "88 Pine Vista",
    address_unit_as_given: "88 Pine Vista · Unit 2",
    units_on_property: 4,
    billing_address_same: true,
    billing_address_as_given: null,
    resolved_premises_id: "01a0a444-5ad2-7e88-be8a-bdb8aa86c05e",
    resolved_unit_id: null,
    resolved_premises_no: "P-00074",
    resolved_unit_no: null,
    resolved_premise_address: "88 Pine Vista",
    premise_locality: { city: "Silver Creek", state: "TX", postal_code: "78611" },
    resolved_match: "exact_reference",
    resolution_kind: "served_vacant",
    plot_or_parcel: null,
    what_is_being_built: null,
    property_type: null,
    no_premise_flag: false,
    lookup_found: null,
    services: [],
    evidence: { premise_exists: true, unit_is_served: false, unit_is_vacant: true },
  },
  documents: {
    documents: [],
    verified: 0,
    attached: 0,
    blocks_creation: false,
    // PO ruling 2026-09-16 — documents are OUTSTANDING, never blocking.
    blocks_approval: false,
    outstanding: true,
    checklist_request_type: null,
    checklist_required: [],
    checklist_unmet: [],
  },
  fees: {
    lines: [],
    outstanding_lines: 0,
    quoted: { amount: "0.0000", display: "0.00", currency: null },
    settled: { amount: "0.0000", display: "0.00", currency: null },
    collected: { amount: "0.0000", display: "0.00", currency: null },
    outstanding: { amount: "0.0000", display: "0.00", currency: null },
    shortfall_is_open_balance: false,
    receipt_no: null,
    collected_at: null,
    quoted_at_collection: null,
    fee_timing: null,
    fee_due_by: null,
    fee_method: null,
    posts_to_ledger: false,
    connection_quote: { raised: false, reason: "raised_after_review" },
  },
  decision: {
    what_they_said: null,
    what_the_lookup_found: null,
    options: [],
    preselected: null,
    undrawn_verdict_absence: { tracks: "OQ-356" },
    conditions: {
      clear: 0,
      total: 4,
      blocking: [],
      conditions: [],
      count_differs_from_design: { designed_total: 5, served_total: 4, tracks: "OQ-355" },
    },
    commit: {
      outcome: null,
      decided_by: null,
      decided_at: null,
      decided_against_evidence: false,
      outcome_kind: null,
      outcome_ref: null,
    },
    disconnect_is_not_a_move_out: {
      rule: "BR-CUS-091",
      move_out: "closes_the_account_and_settles_the_deposit",
      disconnect: "leaves_the_account_open_and_accruing",
    },
    refusal: { reason_code: null, reason: null, message: null },
    more_info: { needed: [], message: null },
    what_approving_will_do: {},
    acknowledgement: { state: null, reason: null, ref: null, sent: false, fee_statement: null },
  },
  history: [],
  unavailable: [],
};

/** The request as SR-26-0016 stood when the PO opened it: one application-fee
 *  line of $70.00, nothing taken. */
const SEVENTY = {
  ...DETAIL,
  fees: {
    ...DETAIL.fees,
    lines: [
      {
        id: FEE_ID,
        line_no: 1,
        charge_code: "CC-REQFEE",
        description: "Application fee",
        basis: "per request",
        quantity: "1",
        unit_amount: { amount: "70.0000", display: "70.00", currency: "USD" },
        amount: { amount: "70.0000", display: "70.00", currency: "USD" },
        waived: false,
        waive_reason: null,
        settled_at: null,
        invoice_ref: null,
      },
    ],
    outstanding_lines: 1,
    quoted: { amount: "70.0000", display: "70.00", currency: "USD" },
    settled: { amount: "0.0000", display: "0.00", currency: "USD" },
    collected: { amount: "0.0000", display: "0.00", currency: "USD" },
    outstanding: { amount: "70.0000", display: "70.00", currency: "USD" },
    shortfall_is_open_balance: true,
  },
};

/** The tenant's own served list — `GET /payments` `methods[]` — and it holds
 *  two tenders the old hand-typed `card · cash · cheque` never offered. */
const METHODS = [
  { id: "m-cash", code: "cash", name: "Cash" },
  { id: "m-check", code: "check", name: "Check" },
  { id: "m-card", code: "card", name: "Card" },
  { id: "m-mo", code: "money_order", name: "Money order" },
];

function till(): CounterRow {
  return {
    code: "CTR-260923-MV",
    owner_name: ME,
    service_centre_name: "Main counter",
    opened_at: "2026-09-23T08:55:00Z",
    closed_at: null,
    close_kind: null,
    declared_at: null,
    declared_by_name: null,
    payment_count: 0,
    taken_total: "0.0000",
    counted_total: null,
    difference: null,
    currency: "USD",
  };
}

interface Posted {
  url: string;
  body: Record<string, unknown>;
}

/**
 * Mount the page and open the modal the way a clerk does.
 *
 * `tillOpen` seeds what `GET /counters?f.mine=1` answered — the banner reads
 * it. `refuse` makes the POST answer the server's till refusal, verbatim in
 * shape: 422, `payments.counter.till_required`, `BR-PAY-1186`.
 */
async function openHandover(opts: {
  tillOpen: boolean;
  refuse?: boolean;
  /** DEF-CUS-6455 — any other refusal envelope the POST should answer with. */
  refusal?: Record<string, unknown>;
}): Promise<Posted[]> {
  const posted: Posted[] = [];
  const me = {
    id: "u-marcus",
    full_name: ME,
    email: "marcus@brazosbendutilities.test",
    phone: null,
    role: "billing_clerk",
    role_name: "Billing Clerk",
    must_change_password: false,
  };
  const rows = opts.tillOpen ? [till()] : [];
  const counters = {
    rows,
    count: rows.length,
    totals: {
      open_now: rows.length,
      open_owner_names: rows.map((row) => row.owner_name ?? ""),
      taken_today: "0.0000",
      taken_today_payment_count: 0,
      not_counted: 0,
      not_counted_oldest: null,
      difference_this_week: "0.0000",
      currency: "USD",
    },
  };
  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/interruption")) {
        return json({ detail: "not found" }, 404);
      }
      if (url.includes("/fee-collection") && (init?.method ?? "GET") === "POST") {
        posted.push({ url, body: JSON.parse(String(init?.body ?? "{}")) });
        if (opts.refusal !== undefined) {
          return json(opts.refusal, 422);
        }
        if (opts.refuse === true) {
          return json(
            {
              code: "BIZ-COMPLETENESS",
              message_key: "payments.counter.till_required",
              params: {},
              field_errors: [],
              br_ref: "BR-PAY-1186",
              trace_id: "t-1",
            },
            422,
          );
        }
        return json(SEVENTY.fees);
      }
      // ⚠ **THE TILL READS ANSWER BY ADDRESS TOO.** Seeding the cache is not
      // enough: a stale query refetches, and a stub that hands the request
      // detail to `GET /counters` makes the banner's read FAIL — which draws
      // the *could not tell* note, not the refusal this file asserts.
      if (url.includes("/counters")) {
        return json(counters);
      }
      if (/\/me(\?|$)/.test(url)) {
        return json(me);
      }
      if (/\/payments(\?|$)/.test(url)) {
        return json({
          results: [],
          count: 0,
          next: null,
          previous: null,
          totals: { currency: "USD" },
          methods: METHODS,
        });
      }
      return json(SEVENTY);
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.me, me);
  queryClient.setQueryData(myOpenCounterQueryKey(), counters);
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/brazosbend/requests/${REQUEST_ID}`]}>
        <Routes>
          <Route
            path="/:tenant/requests/:requestId"
            element={<ServiceRequestDetailPage client={client} />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await screen.findByRole("heading", { level: 1 });
  fireEvent.click(
    screen.getByRole("button", { name: i18n.t("customers.serviceRequest.fees.collect") }),
  );
  await screen.findByRole("dialog");
  return posted;
}

function field<T extends HTMLElement>(id: string): T {
  const found = document.querySelector<T>(`#${id}`);
  if (found === null) {
    throw new Error(`no #${id} in the modal`);
  }
  return found;
}

/** Wait until the method select offers `code`. `card` and `cash` are in the
 *  old hand-typed three AND the served list, so waiting on them lets a case
 *  reach its own assertion at the tip; `money_order` is only in the served
 *  list, so waiting on it IS the served-list assertion. */
async function offers(code: string): Promise<void> {
  await waitFor(() =>
    expect(
      Array.from(field<HTMLSelectElement>("method").options).map((option) => option.value),
    ).toContain(code),
  );
}

async function methodsServed(): Promise<void> {
  await offers("money_order");
}

function submit(): void {
  fireEvent.click(
    screen.getByRole("button", { name: i18n.t("customers.serviceRequest.collect.submit") }),
  );
}

describe("DEF-CUS-6376 · the request fee is taken the way Record a payment takes money", () => {
  afterEach(cleanup);

  /**
   * RED at the tip (`c99bc40ff`): `no #posted_at in the modal` — it asked for
   * an amount, a hand-typed tender and a receipt, and nothing else.
   */
  it("posts the POSTING DATE the clerk typed, and the MEMO", async () => {
    const posted = await openHandover({ tillOpen: true });
    // Proposed, never blank: the tenant's today is in the box already.
    expect(field<HTMLInputElement>("posted_at").value).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    await methodsServed();
    fireEvent.change(field("posted_at"), { target: { value: "2026-09-21" } });
    fireEvent.change(field("method"), { target: { value: "cash" } });
    fireEvent.change(field("receipt_no"), { target: { value: "RCP-26-0016" } });
    fireEvent.change(field("memo"), { target: { value: "Paid by her daughter" } });
    submit();
    await waitFor(() => expect(posted).toHaveLength(1));
    const [first] = posted;
    expect(first?.url).toContain(`/service-requests/${REQUEST_ID}/fee-collection`);
    expect(first?.body).toMatchObject({
      // The amount still owing, proposed as a clerk would type it.
      amount: "70.00",
      method: "cash",
      receipt_no: "RCP-26-0016",
      posted_at: "2026-09-21",
      memo: "Paid by her daughter",
    });
    // Hard rule 2 — money is a STRING on the wire, never a number.
    expect(typeof first?.body.amount).toBe("string");
  });

  /**
   * RED at the tip: `expected [ 'card', 'cash', 'cheque' ] to include
   * 'money_order'` — the three were typed by hand in the page.
   */
  it("offers the tenant's SERVED method list, the one Record a payment reads", async () => {
    await openHandover({ tillOpen: true });
    await methodsServed();
    const values = Array.from(field<HTMLSelectElement>("method").options)
      .map((option) => option.value)
      .filter((value) => value !== "");
    expect(values).toEqual(METHODS.map((method) => method.code));
    expect(values).not.toContain("cheque");
  });

  /**
   * RED at the tip: `no #purpose in the modal`. *"it will take only
   * application fee"* — shown as a fact where Record a payment asks.
   */
  it("fixes what the money is for to the APPLICATION FEE — a fact, not a picker", async () => {
    const posted = await openHandover({ tillOpen: true });
    const purpose = field<HTMLInputElement>("purpose");
    expect(purpose.tagName).toBe("INPUT");
    expect(purpose.readOnly).toBe(true);
    expect(purpose.value).toBe(i18n.t("customers.serviceRequest.collect.purposeApplicationFee"));
    expect(document.querySelector("select#purpose")).toBeNull();
    await methodsServed();
    fireEvent.change(field("method"), { target: { value: "card" } });
    fireEvent.change(field("receipt_no"), { target: { value: "RCP-26-0016" } });
    submit();
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0]?.body).not.toHaveProperty("purpose");
  });

  /**
   * RED at the tip: `no #confirmation in the modal` for a card. The reference
   * is the INSTRUMENT's number; the receipt number is the SLIP's, and both are
   * asked. `card` is in the old three AND the served list, so this fails at
   * the tip on the missing field rather than on the list.
   */
  it("asks for the reference where the method has one, and keeps the receipt number", async () => {
    const posted = await openHandover({ tillOpen: true });
    await offers("card");
    fireEvent.change(field("method"), { target: { value: "card" } });
    expect(field("confirmation")).toBeInTheDocument();
    fireEvent.change(field("method"), { target: { value: "cash" } });
    expect(document.querySelector("#confirmation")).toBeNull();
    await methodsServed();
    fireEvent.change(field("method"), { target: { value: "check" } });
    fireEvent.change(field("confirmation"), { target: { value: "10241" } });
    fireEvent.change(field("receipt_no"), { target: { value: "RCP-26-0016" } });
    submit();
    await waitFor(() => expect(posted).toHaveLength(1));
    expect(posted[0]?.body).toMatchObject({
      method: "check",
      confirmation: "10241",
      receipt_no: "RCP-26-0016",
    });
  });

  /**
   * RED at the tip: `expected null not to be null` — no counter banner at
   * all; the modal said nothing about a till and the server took the cash.
   */
  it("with no till open, cash shows the Start-counter door", async () => {
    await openHandover({ tillOpen: false });
    await offers("cash");
    fireEvent.change(field("method"), { target: { value: "cash" } });
    const banner = await waitFor(() => {
      const found = document.querySelector('[data-counter-banner="none"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    const door = banner.querySelector("a");
    expect(door?.getAttribute("href")).toBe("/brazosbend/payments/counter?start=1");
    // A card needs no till, so nothing is said about one.
    fireEvent.change(field("method"), { target: { value: "card" } });
    expect(document.querySelector("[data-counter-banner]")).toBeNull();
  });

  /**
   * The mirror: with a till open, Record a payment says *"Goes into your
   * counter batch …"*. A request fee joins no batch (A2), so nothing is said.
   *
   * ⚠ **ITS RED AT THE TIP IS NOT ITS OWN, SO IT WAS PROVED RED ANOTHER
   * WAY.** At the tip it fails on the served list (`expected [ 'card', 'cash',
   * 'cheque' ] to include 'money_order'`), and past that the tip drew no banner
   * at all — an absence that would pass for the wrong reason. Its own red proof
   * is a MUTATION: with `announceBatch={false}` removed
   * from `RequestFeeHandoverModal`, this case fails on
   * `[data-counter-banner="open"]` being present — the batch sentence a
   * request fee must not carry. The case above is what proves the banner is
   * mounted at all.
   */
  it("with a till open, it does NOT claim the money goes into the batch", async () => {
    await openHandover({ tillOpen: true });
    await methodsServed();
    fireEvent.change(field("method"), { target: { value: "cash" } });
    await waitFor(() =>
      expect(screen.getByRole("dialog").textContent).toContain(i18n.t("payments.form.postedAt")),
    );
    expect(document.querySelector('[data-counter-banner="open"]')).toBeNull();
    expect(document.querySelector('[data-counter-banner="none"]')).toBeNull();
  });

  /**
   * The server's refusal reaches the clerk as WORDS — the catalogue's
   * *"Start your counter first."* — and the modal stays open.
   *
   * ⚠ **GREEN AT THE TIP TOO, AND SAID SO.** The modal has always rendered a
   * server envelope through `FormModal`; what is new is that the SERVER now
   * refuses, which `06-backend/tests/test_def_cus_6376_request_fee_like_
   * record_payment.py` proves red-first. This case is the guard that the
   * refusal is not swallowed on its way to the screen (`DEF-CUS-6096`'s
   * shape) now that the modal is a component with its own error branch.
   */
  it("the server's till refusal is shown in the modal, in words", async () => {
    await openHandover({ tillOpen: false, refuse: true });
    await offers("cash");
    fireEvent.change(field("amount"), { target: { value: "70.00" } });
    fireEvent.change(field("method"), { target: { value: "cash" } });
    fireEvent.change(field("receipt_no"), { target: { value: "RCP-26-0016" } });
    submit();
    await waitFor(() =>
      expect(screen.getByRole("dialog").textContent).toContain(
        i18n.t("payments.counter.till_required"),
      ),
    );
  });
});

describe("DEF-CUS-6455 · the counter takes the WHOLE fee, or it is waived (OQ-CUS-12624)", () => {
  afterEach(cleanup);

  /**
   * PO, 2026-09-24: *"all or waived"*. The server refuses a short payment and
   * names the whole fee as it stores it (`"130.0000"`, `"USD"`); the clerk must
   * read it as money. RED before the build: the key did not exist and the
   * modal passed `params` straight through, so the dialog read the KEY.
   */
  it("a short payment is refused in words, naming the whole fee at two places", async () => {
    await openHandover({
      tillOpen: true,
      refusal: {
        code: "BIZ-COMPLETENESS",
        message_key: "customers.serviceRequest.feeTakeInFull",
        params: { amount: "130.0000", currency: "USD" },
        field_errors: [],
        br_ref: "BR-CUS-090",
        trace_id: "t-6455",
      },
    });
    await offers("cash");
    fireEvent.change(field("amount"), { target: { value: "25.00" } });
    fireEvent.change(field("method"), { target: { value: "cash" } });
    fireEvent.change(field("receipt_no"), { target: { value: "RCP-26-4471" } });
    submit();
    await waitFor(() =>
      expect(screen.getByRole("dialog").textContent).toContain(
        "Take the full $130.00. Or waive it.",
      ),
    );
    expect(screen.getByRole("dialog").textContent).not.toContain("130.0000");
  });

  it("formats only that refusal's figure and leaves every other envelope alone", () => {
    const other = { message_key: "payments.counter.till_required", params: { amount: "70.0000" } };
    expect(withTheFeeFormatted(other)).toBe(other);
    expect(
      withTheFeeFormatted({
        message_key: "customers.serviceRequest.feeTakeInFull",
        params: { amount: "130.0000", currency: "USD" },
      }).params,
    ).toEqual({ amount: "$130.00", currency: "USD" });
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-6376 · DEF-CUS-6374 · PO 2026-09-23 §3.4 · decision log
//   2026-09-19 (A2) · B14 rules 33, 38, 43
// generated: 2026-09-23 by LANE REQ-FEE
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest this file, red at c99bc40ff and green after
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
