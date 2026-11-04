// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Ruling:   PO 2026-09-23, `OQ-CUS-12616` CLOSED — *"My recommendation: yes - we
//           agreed"*: after Approve the clerk LANDS ON THE JOB just created, for
//           both kinds; a job that could not be raised keeps them on the request
//           with the reason in words; and the request shows WHERE IT WENT.
// Defect:   DEF-CUS-6350
// Rules:    hard-won law 2's mirror (assert the destination by ADDRESS and by the
//           SCREEN it opens, under the real route pattern) · B14 rule 31 (the
//           job's NUMBER on screen, never its id)
// ───────────────────────────────────────────────────────
//
// ⚠ **BOTH KINDS ARE PINNED TOGETHER, ON PURPOSE.** The new connection's
// landing existed (`DEF-CUS-6109`) and the move-in's did not; a suite that
// asserted only the new one would let the old one drift, and a suite that
// asserted only the old one is how the move-in stayed on the request.
//
// ⚠ **MOUNTED UNDER THE REAL `/:tenant/…` PATTERNS, WITH THE DESTINATIONS AS
// ROUTES.** A landing asserted by `toContain` on a string could pass on
// `//moves/…` — the protocol-relative address `DEF-CWP-3925` hid behind. Here
// the destination must be a route that MATCHES and renders its screen marker.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import { MOVE_RECORD_ROUTE, MOVE_RECORD_SCREEN } from "./MoveRecordPage";
import { MOVE_IN_WIZARD_ROUTE } from "./moveShared";
import { NEW_CONNECT_ROUTE } from "./newConnectShared";
import { ServiceRequestDetailPage } from "./ServiceRequestDetailPage";

const REQUEST_ID = "01a09540-7900-7dfa-abf4-b30b3c0fb6b8";
const C = "customers.serviceRequest.condition.";

const CLEAR_TAIL = [
  { key: "no_blocking_arrears", state: "clear", blocking: false, message_key: null, params: {} },
  { key: "fee_settled", state: "clear", blocking: false, message_key: null, params: {} },
];

function preview(kind: "move_in" | "new_connection", keys: string[]) {
  return {
    outcome: kind,
    known: true,
    creates: null,
    carries: null,
    rows: [],
    window: {
      submit: `customers.serviceRequest.approveChecks.submit.${kind}`,
      lines: [
        `customers.serviceRequest.approveChecks.effect.${kind}.first`,
        `customers.serviceRequest.approveChecks.effect.${kind}.second`,
      ],
    },
    conditions: {
      clear: keys.length + 2,
      total: keys.length + 2,
      blocking: [],
      outstanding: [],
      conditions: [
        ...keys.map((key) => ({ key, state: "clear", blocking: false, message_key: `${C}unitFree`, params: {} })),
        ...CLEAR_TAIL,
      ],
    },
  };
}

function detail(state: string, job: unknown) {
  const zero = { amount: "0.0000", display: "0.00", currency: null };
  return {
    header: {
      id: REQUEST_ID,
      request_no: "SR-26-0016",
      number_absence: null,
      state,
      classification: "move_in",
      applicant: "David, Tim",
      address_as_given: "highland park",
      address_unit_as_given: null,
      premise_locality: null,
      lookup_found: null,
      received_at: "2026-09-20T09:22:00Z",
      received_by: null,
      channel: "counter",
      waiting_on: null,
      waiting_since: null,
      requested_start: null,
      queue: state === "approved" ? "move_ins" : null,
      job,
    },
    actions: {
      available: state === "approved" ? [] : ["approve", "refuse", "request_info"],
      can_approve: false,
      approve_blocked_by: ["outcome"],
      can_park: false,
    },
    applicant: {
      name: "David, Tim",
      phone: null,
      email: null,
      language: null,
      person_or_company: null,
      co_applicant: { name: null, email: null, phone: null },
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
      customer_match: { customer_id: null, tier: null, basis: null, confirmed_at: null, may_move_money: false },
    },
    location_and_services: {
      address_as_given: "highland park",
      address_unit_as_given: null,
      units_on_property: null,
      billing_address_same: true,
      billing_address_as_given: null,
      resolved_premises_id: null,
      resolved_unit_id: null,
      resolved_premises_no: null,
      resolved_unit_no: null,
      resolved_premise_address: null,
      premise_locality: null,
      resolved_match: null,
      resolution_kind: "unresolved",
      plot_or_parcel: null,
      what_is_being_built: null,
      property_type: null,
      no_premise_flag: false,
      lookup_found: null,
      services: [],
      evidence: { premise_exists: false, unit_is_served: false, unit_is_vacant: false },
    },
    documents: {
      documents: [],
      verified: 0,
      attached: 0,
      blocks_creation: false,
      blocks_approval: false,
      outstanding: false,
      checklist_request_type: null,
      checklist_required: [],
      checklist_unmet: [],
    },
    fees: {
      lines: [],
      outstanding_lines: 0,
      quoted: zero,
      settled: zero,
      collected: zero,
      outstanding: zero,
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
      conditions: { clear: 0, total: 0, blocking: [], conditions: [], count_differs_from_design: { designed_total: 5, served_total: 4, tracks: "OQ-355" } },
      commit: { outcome: null, decided_by: null, decided_at: null, decided_against_evidence: false, outcome_kind: null, outcome_ref: null },
      disconnect_is_not_a_move_out: { rule: "BR-CUS-091", move_out: "x", disconnect: "y" },
      refusal: { reason_code: null, reason: null, message: null },
      more_info: { needed: [], message: null },
      what_approving_will_do: {
        move_in: preview("move_in", ["premises_on_file", "unit_chosen", "unit_free", "no_other_move_in"]),
        new_connection: preview("new_connection", ["address_not_in_premises", "no_open_request_here"]),
      },
      acknowledgement: { state: null, reason: null, ref: null, sent: false, fee_statement: null },
    },
    history: [],
    unavailable: [],
  };
}

function Where() {
  const location = useLocation();
  return <output data-location={`${location.pathname}${location.search}`} />;
}

function mount(first: unknown, approveAnswer: unknown): void {
  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if ((init?.method ?? "GET") !== "GET") {
        return new Response(JSON.stringify(approveAnswer), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.includes("/interruption")) {
        return new Response(JSON.stringify({ detail: "not found" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify(first), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={[`/brazosbend/requests/${REQUEST_ID}`]}>
        <Where />
        <Routes>
          <Route path="/:tenant/requests/:requestId" element={<ServiceRequestDetailPage client={client} />} />
          <Route
            path={`/:tenant${MOVE_RECORD_ROUTE}`}
            element={<p data-screen={MOVE_RECORD_SCREEN}>move record</p>}
          />
          <Route path={`/:tenant${NEW_CONNECT_ROUTE}`} element={<p data-screen="S87">new connect</p>} />
          {/* `DEF-CUS-7900` — the move-in wizard's standalone address, S19. It
              is a REAL route rather than a string assertion for the reason the
              header of this file gives: a destination asserted only by address
              can pass on a route the router does not mount, and the screen
              then never renders at all. */}
          <Route path={`/:tenant${MOVE_IN_WIZARD_ROUTE}`} element={<p data-screen="S19">move-in wizard</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function approveAs(kind: "move_in" | "new_connection"): Promise<void> {
  await screen.findByRole("heading", { level: 1 });
  fireEvent.click(document.querySelector('[data-decision-action="approve"]') as Element);
  await screen.findByRole("dialog");
  fireEvent.click(document.querySelector(`[data-segment="${kind}"]`) as Element);
  // Inside the DIALOG: the page head carries its own `Approve`, which opens it.
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: i18n.t(`customers.serviceRequest.approveChecks.submit.${kind}`),
    }),
  );
}

function location(): string {
  return document.querySelector("[data-location]")?.getAttribute("data-location") ?? "";
}

describe("OQ-CUS-12616 · after Approve the clerk lands on the job just created", () => {
  afterEach(cleanup);

  // ══════════════════════════════════════════════════════════════════════════
  // `DEF-CUS-7900` (PO 2026-09-29) — THIS CASE USED TO ASSERT THE RECORD
  // ══════════════════════════════════════════════════════════════════════════
  // It read *"a MOVE-IN lands on its own record, by its MVI number"* and
  // expected `/brazosbend/moves/MVI-26-0115`. PO, verbatim: *"when user select
  // the move-in user should redirect on move-in list page or move-in request
  // form"* — so the landing is the WIZARD, carrying this request.
  //
  // ⚠ **`OQ-CUS-12616` IS NARROWED, NOT REVERSED, AND THE DISTINCTION IS WHY
  // THIS COMMENT IS HERE RATHER THAN A DELETED CASE.** That ruling says the
  // clerk lands ON THE JOB JUST CREATED instead of staying on the request, and
  // they still do — on the job's WORK rather than its filing card. The new
  // connection's half below is untouched, which is the symmetry the two kinds
  // never had.
  //
  // **RED-FIRST, AND THE RED IS QUOTED** — run against the old navigation:
  //
  //     AssertionError: expected '/brazosbend/moves/MVI-26-0115' to be
  //       '/brazosbend/move-ins/new?request=01a09540-7900-7dfa-abf4-b30b3c0fb6b8'
  //
  // ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** an assertion on the ADDRESS alone
  // would pass over a route the router does not mount — the address would be
  // in the bar and nothing would render. So the wizard is a REAL route here
  // and the case waits for its screen marker before reading the location, the
  // posture this whole file was written in.
  it("DEF-CUS-9043 · the Approve window carries the customer finder that LINKS a customer on file", async () => {
    mount(detail("submitted", null), {});
    await screen.findByRole("heading", { level: 1 });
    fireEvent.click(document.querySelector('[data-decision-action="approve"]') as Element);
    const dialog = await screen.findByRole("dialog");
    // `DEF-CUS-10043` — the free-text finder became the request-ID search button.
    expect(dialog.querySelector("[data-request-customer-link] [data-customer-search]")).not.toBeNull();
  });

  it("a MOVE-IN lands in the MOVE-IN WIZARD, carrying the request it came from", async () => {
    const approved = {
      ...detail("approved", { kind: "move_in", id: "job-1", number: "MVI-26-0115", state: "pending" }),
      job: {
        raised: {
          kind: "move_in",
          table: "move_in_jobs",
          module: "customers",
          queue: "move_ins",
          id: "job-1",
          ref: "SR-26-0016",
          move_no: "MVI-26-0115",
          state: "pending",
          names_this_request: true,
          warnings: [],
        },
      },
    };
    mount(detail("submitted", null), approved);
    await approveAs("move_in");
    await waitFor(() => expect(document.querySelector('[data-screen="S19"]')).not.toBeNull());
    expect(location()).toBe(`/brazosbend/move-ins/new?request=${REQUEST_ID}`);
    // ⛔ **AND NOT THE RECORD.** Without this the case would pass on a screen
    // that rendered both, or on one that redirected onward a tick later.
    expect(document.querySelector(`[data-screen="${MOVE_RECORD_SCREEN}"]`)).toBeNull();
  });

  // ⚠ **THE NO-SERIES TENANT, AND THE CASE EXISTS BECAUSE ITS FALLBACK IS
  // GONE.** The old branch needed one: a RECORD can only be addressed by a
  // number, and a tenant that keeps no `move_in` series has none, so that clerk
  // was sent to the Move-ins tab to hunt for the row. The WIZARD is addressed
  // by the REQUEST, which this page always has, so there is nothing left to
  // fall back FROM — and an absent fallback is invisible to every check in this
  // repo unless a case names it (`DEF-CUS-3653`). Decision log, 2026-09-29.
  it("a tenant with NO `move_in` series lands on the SAME wizard — no fallback, none needed", async () => {
    const approved = {
      ...detail("approved", { kind: "move_in", id: "job-1", number: null, state: "pending" }),
      job: {
        raised: {
          kind: "move_in",
          table: "move_in_jobs",
          module: "customers",
          queue: "move_ins",
          id: "job-1",
          ref: "SR-26-0016",
          move_no: null,
          state: "pending",
          names_this_request: true,
          warnings: [],
        },
      },
    };
    mount(detail("submitted", null), approved);
    await approveAs("move_in");
    await waitFor(() => expect(document.querySelector('[data-screen="S19"]')).not.toBeNull());
    expect(location()).toBe(`/brazosbend/move-ins/new?request=${REQUEST_ID}`);
    // ⛔ The old destination for this tenant, named so its removal is asserted
    // rather than assumed.
    expect(location()).not.toContain("tab=move-ins");
  });

  it("a NEW CONNECTION lands in its build's wizard, exactly as before", async () => {
    const approved = {
      ...detail("approved", { kind: "connection", id: "con-1", number: "CON-26-0131", state: "draft" }),
      job: {
        raised: {
          kind: "connection",
          table: "connections",
          module: "metering",
          queue: "new_connects",
          id: "con-1",
          ref: "CON-26-0131",
          state: "draft",
          names_this_request: true,
          warnings: [],
        },
      },
    };
    mount(detail("submitted", null), approved);
    await approveAs("new_connection");
    await waitFor(() => expect(document.querySelector('[data-screen="S87"]')).not.toBeNull());
    expect(location()).toBe("/brazosbend/connections/new?build=con-1");
  });

  it("a job that could NOT be raised keeps the clerk on the request, told why in words", async () => {
    const answer = {
      ...detail("approved", null),
      job: { not_raised: { code: "move_in_job_already_raised", br_ref: "BR-CUS-1077" } },
    };
    mount(detail("submitted", null), answer);
    await approveAs("move_in");
    await waitFor(() =>
      expect(document.querySelector('[data-job-not-raised="move_in_job_already_raised"]')).not.toBeNull(),
    );
    expect(location()).toBe(`/brazosbend/requests/${REQUEST_ID}`);
    expect(document.body.textContent).toContain(
      i18n.t("customers.serviceRequest.jobRefusal.move_in_job_already_raised"),
    );
    expect(document.body.textContent).not.toContain("move_in_job_already_raised");
  });
});

describe("the request shows WHERE IT WENT, by number, as a link", () => {
  afterEach(cleanup);

  it("an approved move-in reads 'Approved → Move-in MVI-26-0115' and links to its record", async () => {
    mount(detail("approved", { kind: "move_in", id: "job-1", number: "MVI-26-0115", state: "pending" }), {});
    await screen.findByRole("heading", { level: 1 });
    const link = document.querySelector('[data-request-job-link="MVI-26-0115"]');
    expect(link).not.toBeNull();
    expect(link?.textContent).toBe(
      i18n.t("customers.serviceRequest.approveChecks.approvedTo.move_in", { number: "MVI-26-0115" }),
    );
    expect(link?.getAttribute("href")).toBe("/brazosbend/moves/MVI-26-0115");
    fireEvent.click(link as Element);
    await waitFor(() => expect(document.querySelector(`[data-screen="${MOVE_RECORD_SCREEN}"]`)).not.toBeNull());
  });

  it("a job with no number says so in words — never an id", async () => {
    mount(detail("approved", { kind: "move_in", id: "0a1b2c3d-job", number: null, state: "pending" }), {});
    await screen.findByRole("heading", { level: 1 });
    const line = document.querySelector('[data-request-job="move_in"]');
    expect(line?.textContent).toBe(
      i18n.t("customers.serviceRequest.approveChecks.approvedToUnnumbered.move_in"),
    );
    expect(document.body.textContent).not.toContain("0a1b2c3d");
  });
});
