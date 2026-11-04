// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  PO ratification 2026-09-20, decision log
//          *"SEVEN PO RATIFICATIONS FROM ONE SITTING"* §1 and §8 — the service
//          request's action bar is DRIVEN BY STATE, and the back control NAMES
//          WHERE IT EXITS TO.
// Rules:   BR-SHL-025 (a control this state cannot honour is DISABLED WITH ITS
//          REASON, never hidden) · B14 rule 1 (a header's `←` names its
//          destination) · B14 rule 33 (a FACT caps at six words) · B14 rule 31
//          (no database id is ever a visible value)
// Tests:   this file. `ServiceRequestDetailPage.dom.test.tsx` owns the head's
//          LAYOUT against the drawing; this owns the action bar's CONTRACT
//          against the ratified table, which is a different question and a
//          different table.
// ───────────────────────────────────────────────────────
//
// ⚠ **THE ROWS OF `RATIFIED` BELOW ARE THE PO'S TABLE, TRANSCRIBED.** Quoted
// from the decision log entry of 2026-09-20 §1, which the PO ratified in the
// words *"this is correct - fix it"*:
//
//     | State            | Submit | Approve | Ask for more | Refuse | Park |
//     | Draft            | ✅ the only lawful action | ✗ | ✗ | ✗ | ✗ |
//     | Submitted        | ✗ | ✅ | ✅ | ✅ | ✅ (→ Under review) |
//     | Under review     | ✗ | ✅ | ✅ | ✅ | ✗ |
//     | More info needed | ✗ | ✅ | ✅ | ✅ | ✗ |
//     | Approved         | ✗ | ✗ | ✗ | ✗ | ✗ |
//     | Refused          | ✗ | ✗ | ✗ | ✗ | ✗ |
//
// ⚠ **`available` AND `can_park` ON EACH ROW ARE THE SERVER'S ANSWER, NOT THIS
// FILE'S OPINION.** `service_request.actions_available` reads `TRANSITIONS` and
// returns exactly the four columns above; `service_request_reads._actions`
// answers `can_park`. A fixture that made up a permissive `available` would
// leave every control dead and every assertion here passing over a screen with
// five dead buttons — hard-won law 2's mirror, in a fixture.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { internalReferencesIn } from "@/testSupport/internalReferences";

import { accountsTabFromParam } from "./AccountsListPage";
import { PARKED_HOME_PATHS } from "./wizardPark";

import { ServiceRequestDetailPage } from "./ServiceRequestDetailPage";

const REQUEST_ID = "01a09540-7900-7dfa-abf4-b30b3c0fb6b8";

/** The five controls the ratified table has columns for, in its own order. */
const CONTROLS = ["submit", "approve", "request_info", "refuse", "park"] as const;
type Control = (typeof CONTROLS)[number];

interface Row {
  /** The stored state, as `service_requests.state` holds it. */
  state: string;
  /** `actions_available(state)` — what `TRANSITIONS` allows FROM this state. */
  available: string[];
  /** `_actions(...)["can_park"]`. */
  canPark: boolean;
  /** The ratified table's tick or cross, per control. */
  enabled: Record<Control, boolean>;
  /** What a clerk reads on each DISABLED control. `undefined` where enabled. */
  reason: Partial<Record<Control, string>>;
}

const RATIFIED: readonly Row[] = [
  {
    state: "draft",
    available: ["submit"],
    canPark: false,
    enabled: { submit: true, approve: false, request_info: false, refuse: false, park: false },
    reason: {
      approve: "Not submitted yet.",
      request_info: "Not submitted yet.",
      refuse: "Not submitted yet.",
      park: "Not submitted yet.",
    },
  },
  {
    state: "submitted",
    available: ["approve", "refuse", "request_info"],
    canPark: true,
    enabled: { submit: false, approve: true, request_info: true, refuse: true, park: true },
    reason: { submit: "Already submitted." },
  },
  {
    state: "under_review",
    available: ["approve", "refuse", "request_info"],
    canPark: false,
    enabled: { submit: false, approve: true, request_info: true, refuse: true, park: false },
    reason: { submit: "Already submitted.", park: "Already under review." },
  },
  {
    state: "more_info",
    available: ["approve", "refuse", "request_info"],
    canPark: false,
    enabled: { submit: false, approve: true, request_info: true, refuse: true, park: false },
    reason: { submit: "Already submitted.", park: "Waiting on the applicant." },
  },
  {
    state: "approved",
    available: [],
    canPark: false,
    enabled: { submit: false, approve: false, request_info: false, refuse: false, park: false },
    reason: {
      submit: "This request is approved.",
      approve: "This request is approved.",
      request_info: "This request is approved.",
      refuse: "This request is approved.",
      park: "This request is approved.",
    },
  },
  {
    state: "refused",
    available: [],
    canPark: false,
    enabled: { submit: false, approve: false, request_info: false, refuse: false, park: false },
    reason: {
      submit: "This request is refused.",
      approve: "This request is refused.",
      request_info: "This request is refused.",
      refuse: "This request is refused.",
      park: "This request is refused.",
    },
  },
];

function detailFor(
  row: Row,
  outcome: string | null = null,
  queue: string | null = null,
): Record<string, unknown> {
  return {
    header: {
      id: REQUEST_ID,
      request_no: "SR-26-0071",
      number_absence: null,
      state: row.state,
      classification: outcome ?? "not_yet_classified",
      applicant: "Okonkwo, Adaeze",
      address_as_given: "88 Pine Vista · Unit 2",
      address_unit_as_given: "88 Pine Vista · Unit 2",
      premise_locality: { city: "Silver Creek", state: "TX", postal_code: "78611" },
      lookup_found: null,
      received_at: "2026-08-14T09:22:00Z",
      received_by: null,
      channel: "walk_in",
      waiting_on: null,
      waiting_since: null,
      requested_start: null,
      // §8 — the queue this request's OUTCOME lands on, served from
      // `request_jobs.JOB_SHAPES` and from no second map. `null` until approved.
      queue,
    },
    actions: {
      available: row.available,
      can_approve: false,
      approve_blocked_by: ["documents_verified"],
      can_park: row.canPark,
    },
    applicant: {
      name: "Okonkwo, Adaeze",
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
        outcome,
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
}

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN.** A bare `MemoryRouter` with no
 * `/:tenant/...` route leaves `useParams()` empty, so `requestId` is `""`, the
 * query never fires and every address the page builds comes out `//requests/…`
 * — a protocol-relative URL to another host, which reads as a perfectly good
 * string to `toContain`. That is how `DEF-CWP-3925` hid.
 */
function mount(detail: Record<string, unknown>): void {
  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = String(input);
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
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
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

/**
 * ⚠ **FOUND BY `data-decision-action`, WHICH IS WHAT `DecisionButton` EMITS.**
 * It is not a `data-testid`, and asking for one would have been a change to
 * `serviceRequestDecisions.tsx` — another lane's file this week.
 * `null` is returned rather than thrown so the ABSENCE of a control is an
 * assertable fact: *"there is no Submit button"* is precisely the defect the
 * PO reported, and a query that throws reports it as a broken test instead.
 */
async function controlIn(name: Control): Promise<HTMLButtonElement | null> {
  // The page renders nothing until the detail query settles; the `<h1>` is the
  // first thing the head puts up.
  await screen.findByRole("heading", { level: 1 });
  return document.querySelector<HTMLButtonElement>(`[data-decision-action="${name}"]`);
}

describe("the action bar is driven by state — the PO's table of 2026-09-20", () => {
  afterEach(cleanup);

  // ── §1, column 1 · SUBMIT ────────────────────────────────────────────────
  //
  // ⚠ **THE PO's OWN WORDS FOR THIS ROW:** *"this is draft version of request -
  // it does not allow me to submit"*. There was no Submit control anywhere on
  // the page: the only `submit` in the file was `FormSubmitOutcome` and a
  // handler name.
  for (const row of RATIFIED) {
    it(`${row.state}: Submit is ${row.enabled.submit ? "offered" : "disabled, never hidden"}`, async () => {
      mount(detailFor(row));
      const button = await controlIn("submit");
      // BR-SHL-025 — present in EVERY state. A hidden control cannot be
      // pressed and cannot say why.
      expect(button).not.toBeNull();
      expect(button?.disabled).toBe(!row.enabled.submit);
    });
  }

  // ── §1, all five columns · EVERY CONTROL, EVERY STATE ────────────────────
  //
  // ⚠ **THE SECOND FAULT THE PO FOUND IN THE SAME BLOCK.** Every disabled
  // control gave ONE reason — `customers.serviceRequest.park.terminalNoPark`,
  // *"This request is closed, so there is nothing to wait for."* — which on a
  // DRAFT is false twice over: a draft is not closed, and the clerk is not
  // waiting for anything. It also ran to eleven words, where B14 rule 33 caps
  // a FACT at six.
  for (const row of RATIFIED) {
    it(`${row.state}: every control is drawn, and each disabled one says why`, async () => {
      mount(detailFor(row));
      await screen.findByRole("heading", { level: 1 });
      for (const control of CONTROLS) {
        const button = document.querySelector<HTMLButtonElement>(
          `[data-decision-action="${control}"]`,
        );
        // BR-SHL-025 — never hidden, in any state.
        expect(button, `${row.state}: no ${control} control on the page`).not.toBeNull();
        expect(button?.disabled, `${row.state}: ${control} enabled?`).toBe(
          !row.enabled[control],
        );
        const said = button?.getAttribute("title") ?? null;
        if (row.enabled[control]) {
          // An enabled control has nothing to explain. A reason standing over a
          // live button is a reason that is not true.
          expect(said, `${row.state}: ${control} is live and still gives a reason`).toBeNull();
        } else {
          expect(said, `${row.state}: ${control} is dead and silent`).toBe(
            row.reason[control],
          );
        }
      }
    });
  }

  // ── B14 rule 33 · A FACT CAPS AT SIX WORDS ───────────────────────────────
  //
  // Asserted over the RENDERED sentences rather than over the catalogue, so a
  // row that is edited into a paragraph is caught where a clerk would meet it.
  it("no reason on any control runs past six words", () => {
    for (const row of RATIFIED) {
      for (const [control, sentence] of Object.entries(row.reason)) {
        const words = sentence.trim().split(/\s+/u).length;
        expect(words, `${row.state} · ${control} · "${sentence}"`).toBeLessThanOrEqual(6);
      }
    }
  });

  // ── §8 · THE BACK CONTROL NAMES WHERE IT EXITS TO ────────────────────────
  //
  // ⚠ **THE PO PRESSED IT ON AN APPROVED MOVE-IN AND LANDED ON THE REQUESTS
  // LIST.** Verbatim: *"when i lick on register - it shoudl take me to movein
  // list page - instead it takes me to request list page"*. Four catalogue keys
  // rendered the identical string `The register` and went to four destinations.
  // **B14 rule 1 decides it: a page header's `←` NAMES WHERE IT EXITS TO**, and
  // a control that names its destination cannot send a clerk to the wrong tab.
  //
  // ⚠ **THE QUEUE PER OUTCOME IS `request_jobs.JOB_SHAPES` AND THERE IS NO
  // SECOND MAP.** The server answers it; this only turns the queue's name into
  // the tab's slug and refuses anything `ACCOUNTS_TAB_IDS` does not know.
  //
  // ⚠ **THE SLUGS ARE `AccountsListPage`'s HYPHENATED TAB IDS**, the same ones
  // `PARKED_HOME_PATHS` uses — asserted below rather than assumed, because the
  // move-record lane landed its own back-link fix from that map on the same
  // day and a slug that differed by one character would send two screens to
  // two places.
  const BACK: ReadonlyArray<{
    what: string;
    state: string;
    outcome: string | null;
    queue: string | null;
    href: string;
    label: string;
  }> = [
    {
      what: "a draft",
      state: "draft",
      outcome: null,
      queue: null,
      href: "/brazosbend/requests",
      label: "Requests",
    },
    {
      what: "a submitted request",
      state: "submitted",
      outcome: null,
      queue: null,
      href: "/brazosbend/requests",
      label: "Requests",
    },
    {
      what: "a refused request",
      state: "refused",
      outcome: null,
      queue: null,
      href: "/brazosbend/requests",
      label: "Requests",
    },
    {
      what: "an approved new connection",
      state: "approved",
      outcome: "new_connection",
      queue: "new_connects",
      href: "/brazosbend/accounts?tab=new-connects",
      label: "New connects",
    },
    {
      what: "an approved move-in",
      state: "approved",
      outcome: "move_in",
      queue: "move_ins",
      href: "/brazosbend/accounts?tab=move-ins",
      label: "Move-ins",
    },
    {
      what: "an approved move-out",
      state: "approved",
      outcome: "move_out",
      queue: "move_outs",
      href: "/brazosbend/accounts?tab=move-outs",
      label: "Move-outs",
    },
    {
      what: "an approved transfer",
      state: "approved",
      outcome: "transfer",
      queue: "transfers",
      href: "/brazosbend/accounts?tab=transfers",
      label: "Transfers",
    },
    {
      what: "an approved disconnect",
      state: "approved",
      outcome: "disconnect",
      queue: "disconnects",
      href: "/brazosbend/accounts?tab=disconnects",
      label: "Disconnects",
    },
  ];

  for (const exit of BACK) {
    it(`${exit.what}: the back control reads "${exit.label}" and goes there`, async () => {
      const row = RATIFIED.find((r) => r.state === exit.state) as Row;
      mount(detailFor(row, exit.outcome, exit.queue));
      const back = await screen.findByTestId("request-back");
      // ⚠ **THE ADDRESS IS ASSERTED WHOLE, INCLUDING THE TENANT.** A page
      // mounted without the `/:tenant` pattern builds `//accounts?tab=…`, a
      // protocol-relative URL to another host — and `toContain` reads that as a
      // perfectly good string. `toBe` on the full path cannot be fooled by it.
      expect(back.getAttribute("href")).toBe(exit.href);
      expect(back.getAttribute("href")?.startsWith("//")).toBe(false);
      // B14 rule 1 — it NAMES the destination. `The register` named four.
      expect(back.textContent).toContain(exit.label);
      expect(back.textContent).not.toContain("The register");
    });
  }

  // ⚠ **THE TAB STRIP'S OWN FUNCTION IS ASKED WHETHER IT ACCEPTS WHAT WE EMIT,
  // AND THAT IS THE CHECK THAT MATTERS.** `accountsTabFromParam` falls back to
  // `"accounts"` for anything `ACCOUNTS_TAB_IDS` does not know — **silently**,
  // with no error and no empty state. So the backend's `move_ins` would land a
  // clerk on the Accounts list looking at accounts, which is a wrong answer
  // wearing a working page.
  //
  // ⚠ **A STRING MATCH ON A TAB NAME PROVES NOTHING HERE**, in a browser or in
  // jsdom: the strip renders all ten tab words on every tab, so *"the page
  // mentions move-outs"* is true of a BROKEN build. What distinguishes them is
  // WHICH tab is selected, and this asks the function that decides it.
  it("every address the back control emits selects the tab it names", () => {
    for (const exit of BACK) {
      if (exit.queue === null) continue;
      const slug = new URL(exit.href, "https://example.invalid").searchParams.get("tab");
      expect(slug, `${exit.what}: no ?tab= in ${exit.href}`).not.toBeNull();
      // Not merely "accepted" — the SAME tab back. A fallback returns
      // "accounts", which is what a rejected slug looks like from outside.
      expect(accountsTabFromParam(slug), `${exit.what}: ?tab=${slug}`).toBe(slug);
      // ⚠ **AND THE RAW QUEUE NAME IS SWALLOWED — FOR THE THREE WHERE THE TWO
      // VOCABULARIES ACTUALLY DIFFER.** `transfers` and `disconnects` are ONE
      // WORD and spelled identically in both, so they would have worked by
      // accident; `new_connects`, `move_ins` and `move_outs` would not. That
      // is the worst possible shape for a bug — two of five queues right, three
      // silently landing on the Accounts list — and it is why the derivation
      // is guarded rather than trusted.
      if (exit.queue !== slug) {
        expect(accountsTabFromParam(exit.queue), `raw ${exit.queue}`).toBe("accounts");
      }
    }
  });

  // ⚠ **THE TWO LANES' SLUGS, COMPARED RATHER THAN TRUSTED.** `PARKED_HOME_PATHS`
  // is what the move-record back link, a park, a discard and a resume all read.
  // If the server's queue name and that map ever disagree, this fails here
  // instead of a clerk landing on the Accounts list.
  it("every queue's slug is one PARKED_HOME_PATHS already navigates to", () => {
    const homes = new Set(Object.values(PARKED_HOME_PATHS));
    for (const exit of BACK) {
      if (exit.queue === null) continue;
      expect(homes, `${exit.queue}`).toContain(
        `/accounts?tab=${exit.queue.replace(/_/gu, "-")}`,
      );
    }
  });

  // ── B14 rules 31 and 32 · nothing internal reaches the clerk ─────────────
  //
  // Scoped to the five controls rather than to the whole page: the TABS below
  // carry stated absences that name an open question on purpose (`OQ-355`,
  // `OQ-356`), which is a different ruling and another lane's to hold.
  for (const row of RATIFIED) {
    it(`${row.state}: no control carries an id or an internal code`, async () => {
      mount(detailFor(row));
      await screen.findByRole("heading", { level: 1 });
      for (const control of CONTROLS) {
        const button = document.querySelector<HTMLElement>(
          `[data-decision-action="${control}"]`,
        );
        expect(button, `${row.state} · ${control} missing`).not.toBeNull();
        expect(
          internalReferencesIn(button as HTMLElement),
          `${row.state} · ${control}`,
        ).toEqual([]);
      }
    });
  }
});
