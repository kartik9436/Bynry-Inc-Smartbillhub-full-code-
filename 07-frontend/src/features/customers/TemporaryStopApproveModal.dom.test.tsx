// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-183-BRC10 T3 — a *Temporary stop* request opens ITS OWN Approve
//           window on the request page, mounted under the real route.
// Rules:    BR-CUS-1120 · BR-CUS-1121 · B14 rules 31, 33, 43 · BR-SHL-025
// ───────────────────────────────────────────────────────
//
// The PO's report on SR-26-0017: a portal stop ask could be approved only as a
// New connection or a Move-in. These cases read the rendered DOM a clerk reads.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import { ServiceRequestDetailPage } from "./ServiceRequestDetailPage";

const REQUEST_ID = "01a09540-7900-7dfa-abf4-b30b3c0fb6b8";

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

function stopDetail(problems: { code: string; message_key: string; params: Record<string, unknown> }[]) {
  return {
    ...DETAIL,
    header: { ...DETAIL.header, request_no: "SR-26-0017", classification: "temporary_stop" },
    actions: { ...DETAIL.actions, available: ["approve", "refuse", "request_info"] },
    temporary_stop: {
      kind: "temporary_stop",
      limits: { min_days: 10, max_months: 12 },
      problems,
      stop: {
        id: "01a0b000-0000-7000-8000-000000000001",
        account_id: "01a0b000-0000-7000-8000-000000000002",
        account_no: "AC-2026-00551",
        status: "requested",
        channel: "customer_portal",
        stop_from: "2026-10-13",
        restart_on: "2026-10-16",
        days: 3,
        reason: "away",
        field_visit_needed: false,
        shutoff_order_no: null,
        turnon_order_no: null,
        ended_early: false,
        billed_during_hold: "base_only",
        request_no: "SR-26-0017",
        request_id: REQUEST_ID,
        restart_request_no: null,
        restart_request_id: null,
        restart_request_state: null,
      },
    },
  };
}

const posts: { url: string; body: unknown }[] = [];

function mount(detail: unknown): void {
  posts.length = 0;
  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if ((init?.method ?? "GET") !== "GET") {
        posts.push({ url, body: JSON.parse(String(init?.body ?? "{}")) });
        return new Response(
          JSON.stringify({ ...(detail as object), temporary_stop_result: { warnings: [] } }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/interruption")) {
        return new Response(JSON.stringify({ detail: "not found" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify(detail), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
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
}

async function openApprove(detail: unknown): Promise<HTMLElement> {
  mount(detail);
  await screen.findByRole("heading", { level: 1 });
  fireEvent.click(document.querySelector('[data-decision-action="approve"]') as Element);
  return screen.findByRole("dialog");
}

describe("CR-183 — a temporary stop is approved in its own window", () => {
  afterEach(cleanup);

  it("the request is typed Temporary stop, not Not yet classified", async () => {
    mount(stopDetail([]));
    await screen.findByRole("heading", { level: 1 });
    expect(document.body.textContent).toContain(
      i18n.t("customers.serviceRequest.type.temporary_stop"),
    );
    expect(document.body.textContent).not.toContain(
      i18n.t("customers.serviceRequest.type.notYetClassified"),
    );
  });

  it("offers no New connection or Move-in, and shows account, base-only and the tick", async () => {
    const dialog = await openApprove(stopDetail([]));
    expect(dialog.querySelector("[data-outcome-picker]")).toBeNull();
    expect(within(dialog).queryByText(i18n.t("customers.serviceRequest.approveChecks.kindOption.move_in"))).toBeNull();
    expect(dialog.textContent).toContain("AC-2026-00551");
    expect(dialog.textContent).toContain(i18n.t("customers.temporaryStop.fact.baseOnly"));
    expect(
      within(dialog).getByLabelText(i18n.t("customers.temporaryStop.field.fieldVisit")),
    ).toBeInTheDocument();
    // Internal ids never reach the clerk (B14 rule 31), and every figure is
    // filled — the walk caught `{{days}} days` on screen (2026-10-14).
    expect(dialog.textContent).not.toContain("01a0b000");
    expect(dialog.textContent).toContain(i18n.t("customers.temporaryStop.fact.days", { days: 3 }));
    expect(dialog.textContent).not.toContain("{{");
  });

  it("a three-day ask is refused before the press, with the server's words", async () => {
    const dialog = await openApprove(
      stopDetail([
        {
          code: "too_short",
          message_key: "customers.temporaryStop.tooShort",
          params: { min_days: 10, days: 3 },
        },
      ]),
    );
    const sentence = i18n.t("customers.temporaryStop.tooShort", { min_days: 10 });
    expect(dialog.textContent).toContain(sentence);
    const submit = within(dialog).getByRole("button", {
      name: i18n.t("customers.temporaryStop.approve.submit"),
    });
    expect(submit).toBeDisabled();
  });

  it("approving posts the ticked field visit to the temporary-stop door", async () => {
    const detail = stopDetail([]);
    detail.temporary_stop.stop.restart_on = "2026-10-30";
    detail.temporary_stop.stop.days = 17;
    const dialog = await openApprove(detail);
    fireEvent.click(within(dialog).getByLabelText(i18n.t("customers.temporaryStop.field.fieldVisit")));
    fireEvent.click(
      within(dialog).getByRole("button", { name: i18n.t("customers.temporaryStop.approve.submit") }),
    );
    await waitFor(() => expect(posts).toHaveLength(1));
    expect(posts[0]?.url).toContain(`/service-requests/${REQUEST_ID}/temporary-stop/approve`);
    expect(posts[0]?.body).toMatchObject({
      stop_from: "2026-10-13",
      restart_on: "2026-10-30",
      field_visit_needed: true,
    });
    // The window closes on success (the walk found it left open).
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
