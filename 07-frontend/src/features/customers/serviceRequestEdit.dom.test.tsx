// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   PO ruling 2026-09-23, verbatim: *"if user makes mistake while
//           filling t new request form then system should allow to correct it
//           using edit , there is no edit available on list view as wellas
//           detail view"* — decision log *"THE PO ASKS FOR *EDIT* ON A SERVICE
//           REQUEST, AND WHY IT CANNOT BE THE NEXT THING WIRED"*. Lane REQ-EDIT.
// Defects:  DEF-CUS-6427 (no Edit door) · DEF-CUS-5880 (a reopened request
//           loads EMPTY) · DEF-CUS-5881 (nothing links to the reopen path).
// Replaces: `serviceRequestResumeHold.test.ts`, which failed the build if
//           anything linked to the wizard for an EXISTING request. Its header
//           instructed exactly this: fix the hydration first, then delete it in
//           the same commit that wires the door. The four things it was
//           protecting are asserted here instead, directly:
//             (a) the wizard LOADS the saved request, every step;
//             (b) a MASKED value is never sent back — the mask is not a value;
//             (c) changing ONE field sends ONE field, and blanks nothing;
//             (d) the door exists only while the request is still being
//                 worked, and the server refuses an edit after that.
// Harness:  every screen is mounted under its REAL route pattern
//           (`/:tenant/requests…`), so `useTenantPath` builds `/brazosbend/…`
//           and never `//…` — hard-won law 2's fixture clause. The server is a
//           fake that holds ONE stored request and applies a PATCH the way
//           `update_request` does: only the keys it is sent.
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import {
  ServiceRequestCapturePage,
  captureStepNumber,
  changedCapturePayload,
  clearOtherKind,
  hydrateCaptureForm,
  serviceStartsPayload,
} from "./ServiceRequestCapturePage";
import type { ServiceRequestDetail } from "./serviceRequestEndpoints";
import { ServiceRequestDetailPage } from "./ServiceRequestDetailPage";
import { ServiceRequestsListPage } from "./ServiceRequestsListPage";
import type { ServiceRequestRow } from "./serviceRequestEndpoints";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);
const TENANT = "brazosbend";
const ID = "sr-48";

// ══════════════════════════════════════════════════════════════════════════
// THE STORED REQUEST — what the server holds, in the server's own terms
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **THE FULL SSN AND LICENCE ARE HERE AND ONLY HERE.** The fake server holds
// them the way `ServiceRequest.ssn` does and serves the LAST FOUR, exactly as
// `service_request_reads` calls `crypto.last_four()` — so a test that finds a
// full number anywhere on the wire or on the screen has found a real leak.
interface Stored {
  state: string;
  applicant_kind: string;
  applicant_name: string;
  applicant_email: string;
  applicant_phone: string;
  ssn: string;
  drivers_licence: string;
  date_of_birth: string;
  requested_start: string;
  address_as_given: string;
  address_unit_as_given: string;
  address_city_as_given: string;
  address_state_as_given: string;
  address_postal_code_as_given: string;
  billing_address_same: boolean;
  billing_line1_as_given: string;
  billing_line2_as_given: string;
  billing_city_as_given: string;
  billing_state_as_given: string;
  billing_postal_code_as_given: string;
  what_they_said: string;
  [key: string]: unknown;
}

function storedRequest(over: Partial<Stored> = {}): Stored {
  return {
    state: "submitted",
    applicant_kind: "person",
    applicant_name: "Dana Whitfield",
    applicant_email: "dana.whitfield@example.com",
    applicant_phone: "512-555-0100",
    ssn: "123-45-5236",
    drivers_licence: "TX44179566",
    date_of_birth: "1984-03-02",
    requested_start: "2026-10-14",
    address_as_given: "212 Balcones Drive",
    address_unit_as_given: "3",
    address_city_as_given: "Austin",
    address_state_as_given: "TX",
    address_postal_code_as_given: "78704",
    billing_address_same: false,
    billing_line1_as_given: "PO Box 4471",
    billing_line2_as_given: "",
    billing_city_as_given: "Round Rock",
    billing_state_as_given: "TX",
    billing_postal_code_as_given: "78664",
    what_they_said: "Moving in on the 14th",
    ...over,
  };
}

function lastFour(value: string): string | null {
  const cleaned = value.replace(/[^0-9A-Za-z]/g, "");
  return cleaned === "" ? null : cleaned.slice(-4);
}

const money = (amount: string) => ({
  amount,
  display: amount.slice(0, amount.indexOf(".") + 3),
  currency: "USD",
});

function detailOf(stored: Stored) {
  const nul = (value: string) => (value === "" ? null : value);
  return {
    header: {
      id: ID,
      request_no: "SR-26-0048",
      number_absence: null,
      state: stored.state,
      classification: "not_yet_classified",
      applicant: stored.applicant_name,
      address_as_given: stored.address_as_given,
      address_unit_as_given: stored.address_unit_as_given,
      premise_locality: null,
      lookup_found: null,
      received_at: "2026-09-23T09:00:00Z",
      received_by: "user-1",
      channel: "walk_in",
      waiting_on: null,
      waiting_since: null,
      requested_start: nul(stored.requested_start),
      queue: null,
    },
    actions: {
      available: stored.state === "draft" ? ["submit"] : ["approve", "refuse", "request_info"],
      can_approve: false,
      approve_blocked_by: [],
      can_park: true,
    },
    applicant: {
      name: nul(stored.applicant_name),
      phone: nul(stored.applicant_phone),
      email: nul(stored.applicant_email),
      language: null,
      person_or_company: stored.applicant_kind,
      customer_category: {
        account_type: { id: "at-1", code: "residential", name: "Residential" },
        account_subtype: null,
        not_yet_categorised: false,
      },
      co_applicant: { name: null, email: null, phone: null },
      identifier: {
        ssn_last4: lastFour(stored.ssn),
        ssn_present: stored.ssn !== "",
        stored_encrypted: stored.ssn !== "",
        drivers_licence_last4: lastFour(stored.drivers_licence),
        drivers_licence_present: stored.drivers_licence !== "",
        drivers_licence_stored_encrypted: stored.drivers_licence !== "",
      },
      date_of_birth: nul(stored.date_of_birth),
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
      address_as_given: stored.address_as_given,
      address_unit_as_given: nul(stored.address_unit_as_given),
      address_city_as_given: nul(stored.address_city_as_given),
      address_state_as_given: nul(stored.address_state_as_given),
      address_postal_code_as_given: nul(stored.address_postal_code_as_given),
      units_on_property: null,
      billing_address_same: stored.billing_address_same,
      billing_address_as_given: null,
      billing_line1_as_given: nul(stored.billing_line1_as_given),
      billing_line2_as_given: nul(stored.billing_line2_as_given),
      billing_city_as_given: nul(stored.billing_city_as_given),
      billing_state_as_given: nul(stored.billing_state_as_given),
      billing_postal_code_as_given: nul(stored.billing_postal_code_as_given),
      resolved_premises_id: null,
      resolved_unit_id: null,
      resolved_premises_no: null,
      resolved_unit_no: null,
      resolved_premise_address: null,
      premise_locality: null,
      resolved_match: null,
      resolution_kind: "unresolved",
      lookup_found: null,
      plot_or_parcel: null,
      what_is_being_built: null,
      property_type: null,
      no_premise_flag: false,
      services: [
        { code: "water", requested_start: "2026-10-14", available: null },
        { code: "sewer", requested_start: "2026-11-02", available: null },
      ],
      requested_start_agreement: { count: 2, agreed: null, unset: 0 },
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
      lines: [
        {
          id: "fee-1",
          line_no: 1,
          charge_code: "CC-REQFEE",
          description: "Application processing fee",
          basis: "per request",
          quantity: "1.0000",
          unit_amount: money("25.0000"),
          amount: money("25.0000"),
          waived: false,
          waive_reason: null,
          settled_at: null,
          invoice_ref: null,
        },
      ],
      outstanding_lines: 1,
      quoted: money("25.0000"),
      settled: money("0.0000"),
      collected: money("0.0000"),
      outstanding: money("25.0000"),
      shortfall_is_open_balance: true,
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
      what_they_said: nul(stored.what_they_said),
      what_the_lookup_found: null,
      options: [],
      refusal: { reason_code: null, reason: null, message: null },
      more_info: { needed: [], message: null },
      what_approving_will_do: {},
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
      disconnect_is_not_a_move_out: { rule: "BR-CUS-091", move_out: "x", disconnect: "y" },
      acknowledgement: { state: null, reason: null, ref: null, sent: false, fee_statement: null },
    },
    history: [],
    unavailable: [],
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

interface Call {
  method: string;
  path: string;
  body: Record<string, unknown> | null;
}

/** The fake server. A PATCH is applied the way `update_request` applies it —
 *  **only the keys it carries** — so a blank sent is a blank stored, and a key
 *  not sent is left alone. That is the whole difference this suite is about. */
function makeServer(stored: Stored, rows: ServiceRequestRow[] = []) {
  const calls: Call[] = [];
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "http://x");
      const path = url.pathname.replace(/^\/api\/brazosbend/, "");
      const method = (init?.method ?? "GET").toUpperCase();
      const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null;
      calls.push({ method, path, body });
      if (method === "GET") {
        if (path === `/service-requests/${ID}`) return json(detailOf(stored));
        if (path === `/service-requests/${ID}/interruption`) return json({ detail: "x" }, 404);
        if (path === "/service-requests") {
          return json({
            count: rows.length,
            next: null,
            previous: null,
            results: rows,
            kpis: {
              open: rows.length,
              waiting_on_customer: 0,
              oldest_waiting: { days: null, request_no: null, waiting_on: null },
              approved_not_started: 0,
              refused_this_month: 0,
              period_basis: "server_month_to_date",
            },
            segment: "all",
          });
        }
        if (path === "/service-requests/categories") {
          return json({ selectable: [{ code: "residential", name: "Residential" }], legacy: [] });
        }
        if (path === "/settings/services") {
          return json([
            { service: "water", name: "Water", enabled: true },
            { service: "sewer", name: "Sewer", enabled: true },
          ]);
        }
        if (path === "/service-requests/capture-defaults") {
          return json({ requested_start: "2026-10-15", working_days: 15, holidays_counted: 0 });
        }
        if (path === "/premises/picker") {
          // DEF-CUS-9041 — the register's own search, answering only for a
          // query that names the street the applicant typed.
          const q = url.searchParams.get("q") ?? "";
          const hit = q.toLowerCase().includes("balcones");
          return json({
            count: hit ? 1 : 0,
            next: null,
            previous: null,
            results: hit
              ? [
                  {
                    id: "prem-212",
                    premise_no: "P-00212",
                    address_line: "212 Balcones Drive",
                    city: "Austin",
                    state: "TX",
                    postal_code: "78704",
                    services_available: ["water", "sewer"],
                    premises_type: "apartment_complex",
                    units: [
                      { id: "unit-1", unit_no: "U-00001", label: "Unit 1", is_common_area: false },
                      { id: "unit-3", unit_no: "U-00003", label: "Unit 3", is_common_area: false },
                    ],
                  },
                ]
              : [],
          });
        }
        return json({ count: 0, next: null, previous: null, results: [] });
      }
      if (method === "PATCH" && path === `/service-requests/${ID}`) {
        for (const [key, value] of Object.entries(body ?? {})) {
          stored[key] = value === null ? "" : value;
        }
        return json(detailOf(stored));
      }
      return json(detailOf(stored));
    },
  });
  return { calls, client, stored };
}

function Where() {
  const location = useLocation();
  return <output data-testid="where">{`${location.pathname}${location.search}`}</output>;
}

function mountAt(client: ReturnType<typeof createApiClient>, entry: string): void {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          {/* The four routes in App.tsx's order: the static `new` is declared
              BEFORE `:requestId`, as the real router declares it. */}
          <Route
            path="/:tenant/requests/new"
            element={
              <>
                <ServiceRequestCapturePage client={client} />
                <Where />
              </>
            }
          />
          <Route
            path="/:tenant/requests"
            element={<ServiceRequestsListPage client={client} />}
          />
          <Route
            path="/:tenant/requests/:requestId"
            element={<ServiceRequestDetailPage client={client} />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const input = (id: string) => document.getElementById(id) as HTMLInputElement;

async function loaded(): Promise<void> {
  await waitFor(() => expect(input("full_name")).toHaveValue("Dana Whitfield"));
}

function patches(calls: Call[]): Call[] {
  return calls.filter((call) => call.method === "PATCH");
}

// ══════════════════════════════════════════════════════════════════════════
// PURE — the load and the difference, without a screen
// ══════════════════════════════════════════════════════════════════════════

describe("hydrateCaptureForm / changedCapturePayload — the two halves of a safe edit", () => {
  const loaded = () =>
    hydrateCaptureForm(detailOf(storedRequest()) as unknown as ServiceRequestDetail);

  it("loads every step's facts, the masked pair as LAST FOUR only, and each service's own date", () => {
    const form = loaded();
    expect(form).toMatchObject({
      applicant_name: "Dana Whitfield",
      applicant_phone: "512-555-0100",
      date_of_birth: "1984-03-02",
      ssn: "",
      ssn_on_file: "5236",
      drivers_licence: "",
      drivers_licence_on_file: "9566",
      account_type_code: "residential",
      requested_start: "2026-10-14",
      services: ["water", "sewer"],
      billing_address_same: false,
      what_they_said: "Moving in on the 14th",
    });
    // Water's date IS the job's, so it follows it; sewer's is its own.
    expect(form.service_starts).toEqual({ sewer: "2026-11-02" });
    expect(serviceStartsPayload(form)).toEqual([
      { code: "water", requested_start: "2026-10-14" },
      { code: "sewer", requested_start: "2026-11-02" },
    ]);
  });

  it("nothing changed → nothing sent", () => {
    const form = loaded();
    expect(changedCapturePayload(form, { ...form })).toEqual({});
  });

  it("switching to a company CLEARS the stored identifiers — by sending empty, never a mask", () => {
    const form = loaded();
    const next = { ...form, ...clearOtherKind(form, "business") };
    expect(changedCapturePayload(form, next)).toEqual({
      applicant_kind: "business",
      date_of_birth: null,
      ssn: "",
      drivers_licence: "",
    });
  });

  it("clearing the job date is sent as null — `undefined` would vanish from the JSON", () => {
    const form = loaded();
    expect(changedCapturePayload(form, { ...form, requested_start: "" })).toMatchObject({
      requested_start: null,
    });
  });

  it("a pick travels as a PAIR — clearing only the unit must not undo the premises", () => {
    const form = { ...loaded(), picked_premises_id: "p-1", picked_unit_id: "u-3" };
    expect(changedCapturePayload(form, { ...form, picked_unit_id: "" })).toEqual({
      picked_premises_id: "p-1",
      picked_unit_id: null,
    });
  });
});

// ══════════════════════════════════════════════════════════════════════════
// (a) · THE WIZARD LOADS THE SAVED REQUEST — DEF-CUS-5880
// ══════════════════════════════════════════════════════════════════════════

describe("(a) opening the wizard on a saved request LOADS it — DEF-CUS-5880", () => {
  it("step 1 holds the applicant as stored — name, email, phone, kind", async () => {
    const { client } = makeServer(storedRequest());
    mountAt(client, `/${TENANT}/requests/new?request=${ID}`);
    await loaded();
    expect(input("email")).toHaveValue("dana.whitfield@example.com");
    expect(input("phone")).toHaveValue("512-555-0100");
  });

  it("the PROPERTY step holds the service address and the billing address PARTS as stored", async () => {
    // ⊕ **AMENDED 2026-09-29 (`5e18b70a7`, REQ-03 — New Request in four
    // steps).** The six steps `customer · connection · addresses · documents ·
    // fees · check` became `applicant · property · service · review`, and old
    // step 3 · *addresses* is now **`property`**. Nothing this case asks for
    // moved OFF the wizard — only its page number changed — so every
    // assertion below is untouched.
    //
    // ⚠ **THE NUMBER IS DERIVED AND THE TITLE NAMES THE STEP.** A literal `3`
    // is right until the flow moves and then it silently opens another screen
    // whose fields are simply absent, which is what this line did. The page
    // itself gives `captureStepNumber` for exactly this reason and says so on
    // the constant.
    // ⊕ **AMENDED 2026-10-18 (lane CF-1).** The mailing address moved to the
    // APPLICANT step with the rest of the shared customer form (drawing set
    // `customer-forms-2026-10-18`, image 03); its parts are read there, and
    // the service address is still on the property step.
    const { client } = makeServer(storedRequest());
    mountAt(client, `/${TENANT}/requests/new?request=${ID}&step=${captureStepNumber("applicant")}`);
    await waitFor(() => expect(input("mailing_line1")).toHaveValue("PO Box 4471"));
    expect(input("mailing_city")).toHaveValue("Round Rock");
    expect(input("mailing_postal_code")).toHaveValue("78664");
    cleanup();
    mountAt(
      makeServer(storedRequest()).client,
      `/${TENANT}/requests/new?request=${ID}&step=${captureStepNumber("property")}`,
    );
    await waitFor(() => expect(screen.getByDisplayValue("212 Balcones Drive")).toBeInTheDocument());
    expect(screen.getByDisplayValue("Austin")).toBeInTheDocument();
  });

  it("the SERVICE step shows the fee already quoted — and a SUBMITTED request's fee is waived, never removed (OQ-357)", async () => {
    // ⊕ **AMENDED 2026-09-29 (`5e18b70a7`, REQ-03).** Old step 5 · *fees* is
    // folded into **`service`** with the rest of the old `connection` step.
    // Re-pointed by name, for the reason above; the fee table, its row and the
    // refused ✕ are all asked for exactly as before.
    const { client } = makeServer(storedRequest());
    mountAt(
      client,
      `/${TENANT}/requests/new?request=${ID}&step=${captureStepNumber("service")}`,
    );
    const table = await waitFor(() => {
      const found = document.querySelector('[data-editable-table="application-fees"]');
      expect(found).not.toBeNull();
      return found as HTMLElement;
    });
    expect(within(table).getByText("Application processing fee")).toBeInTheDocument();
    // The ✕ is refused in words — the server refuses `feeRemoveNotDraft` too.
    const remove = within(table).getByRole("button", {
      name: new RegExp(t("customers.serviceRequest.fees.remove")),
    });
    expect(remove).toBeDisabled();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// (b) · A MASKED VALUE IS NEVER SENT BACK
// ══════════════════════════════════════════════════════════════════════════

describe("(b) the SSN and licence show their mask and the mask is never sent", () => {
  it("the boxes are EMPTY and show the stored last four as their placeholder", async () => {
    const { client } = makeServer(storedRequest());
    mountAt(client, `/${TENANT}/requests/new?request=${ID}`);
    await loaded();
    expect(input("ssn")).toHaveValue("");
    expect(input("ssn")).toHaveAttribute("placeholder", "••• ••• • 5236");
    expect(input("driving_licence")).toHaveValue("");
    expect(input("driving_licence")).toHaveAttribute("placeholder", "•••••9566");
    // The full numbers never reach the page at all.
    expect(document.body.innerHTML).not.toContain("123-45-5236");
    expect(document.body.innerHTML).not.toContain("TX44179566");
  });

  it("a save that did not touch them sends neither key — and no mask glyph anywhere", async () => {
    const { calls, client, stored } = makeServer(storedRequest());
    mountAt(client, `/${TENANT}/requests/new?request=${ID}`);
    await loaded();
    fireEvent.change(input("phone"), { target: { value: "512-555-0199" } });
    fireEvent.click(screen.getByRole("button", { name: t("customers.serviceRequest.capture.saveChanges") }));
    await waitFor(() => expect(patches(calls)).toHaveLength(1));
    const body = patches(calls)[0].body ?? {};
    expect(body).not.toHaveProperty("ssn");
    expect(body).not.toHaveProperty("drivers_licence");
    expect(JSON.stringify(body)).not.toContain("•");
    expect(stored.ssn).toBe("123-45-5236");
    expect(stored.drivers_licence).toBe("TX44179566");
  });

  it("a NEW number typed over the mask is sent, and only that", async () => {
    const { calls, client, stored } = makeServer(storedRequest());
    mountAt(client, `/${TENANT}/requests/new?request=${ID}`);
    await loaded();
    fireEvent.change(input("ssn"), { target: { value: "987-65-4321" } });
    fireEvent.click(screen.getByRole("button", { name: t("customers.serviceRequest.capture.saveChanges") }));
    await waitFor(() => expect(patches(calls)).toHaveLength(1));
    expect(patches(calls)[0].body).toEqual({ ssn: "987-65-4321" });
    expect(stored.drivers_licence).toBe("TX44179566");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// (c) · ONE FIELD CHANGED, ONE FIELD SENT — nothing blanked
// ══════════════════════════════════════════════════════════════════════════

describe("(c) changing one field leaves every other stored value intact", () => {
  it("THE DEF-CUS-5880 MECHANISM: retyping the name and the phone must not blank email or SSN", async () => {
    // ⚠ **THIS IS THE CLERK THE DECISION LOG DESCRIBES**, in the order they
    // act: the wizard opens, they retype the name and the new phone, and save.
    // At the tip the boxes were EMPTY, so the PATCH carried
    // `applicant_email: ""` and `ssn: ""` over the stored values.
    const { calls, client, stored } = makeServer(storedRequest());
    mountAt(client, `/${TENANT}/requests/new?request=${ID}`);
    await waitFor(() => expect(input("full_name")).toBeInTheDocument());
    await waitFor(() => expect(calls.some((c) => c.path === `/service-requests/${ID}`)).toBe(true));
    fireEvent.change(input("full_name"), { target: { value: "Dana Whitfield" } });
    fireEvent.change(input("phone"), { target: { value: "512-555-0199" } });
    const save = screen.getByRole("button", {
      name: new RegExp(
        `${t("customers.serviceRequest.capture.saveChanges")}|${t("customers.serviceRequest.capture.saveAsDraft")}`,
      ),
    });
    fireEvent.click(save);
    await waitFor(() => expect(patches(calls).length).toBeGreaterThan(0));
    expect(stored.applicant_phone).toBe("512-555-0199");
    expect(stored.applicant_email).toBe("dana.whitfield@example.com");
    expect(stored.ssn).toBe("123-45-5236");
    expect(stored.drivers_licence).toBe("TX44179566");
    expect(stored.billing_line1_as_given).toBe("PO Box 4471");
    expect(stored.what_they_said).toBe("Moving in on the 14th");
  });

  it("the PATCH carries exactly the one key that changed — and no side call fires", async () => {
    const { calls, client } = makeServer(storedRequest());
    mountAt(client, `/${TENANT}/requests/new?request=${ID}`);
    await loaded();
    fireEvent.change(input("phone"), { target: { value: "512-555-0199" } });
    fireEvent.click(screen.getByRole("button", { name: t("customers.serviceRequest.capture.saveChanges") }));
    await waitFor(() => expect(patches(calls)).toHaveLength(1));
    expect(patches(calls)[0].body).toEqual({ applicant_phone: "512-555-0199" });
    // The services, the category and the resolver each have their own write
    // and their own audit row; none of them changed, so none of them is sent.
    const posts = calls.filter((call) => call.method === "POST").map((call) => call.path);
    expect(posts).toEqual([]);
  });

  it("after saving a submitted request the clerk lands back on its own page", async () => {
    const { client } = makeServer(storedRequest());
    mountAt(client, `/${TENANT}/requests/new?request=${ID}`);
    await loaded();
    fireEvent.change(input("phone"), { target: { value: "512-555-0199" } });
    fireEvent.click(screen.getByRole("button", { name: t("customers.serviceRequest.capture.saveChanges") }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 1, name: "Dana Whitfield" })).toBeInTheDocument(),
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════
// (d) · THE DOOR — only while the request is still being worked
// ══════════════════════════════════════════════════════════════════════════

function row(id: string, state: string): ServiceRequestRow {
  return {
    id,
    request_no: `SR-26-${id.slice(-4)}`,
    number_absence: null,
    type: null,
    type_absence: { reason: "not_yet_decided" },
    applicant: `Applicant ${id}`,
    address: "212 Balcones Drive",
    address_unit: null,
    received_at: "2026-09-23T09:00:00Z",
    channel: "walk_in",
    age_days: 0,
    age_is_accented: false,
    waiting_on: null,
    state,
  };
}

const ROWS = [
  row("sr-0001", "draft"),
  row("sr-0002", "submitted"),
  row("sr-0003", "under_review"),
  row("sr-0004", "more_info"),
  row("sr-0005", "approved"),
  row("sr-0006", "refused"),
];

function rowOf(requestNo: string): HTMLElement {
  return screen.getByText(requestNo).closest("tr") as HTMLElement;
}

describe("(d) Edit and Resume are doors only while the request is being worked", () => {
  it("the list: Resume on a draft, Edit while submitted · under review · more info — by ADDRESS", async () => {
    const { client } = makeServer(storedRequest(), ROWS);
    mountAt(client, `/${TENANT}/requests?segment=all`);
    await screen.findByText("SR-26-0001");
    const resume = within(rowOf("SR-26-0001")).getByRole("link", {
      name: t("customers.serviceRequest.action.resumeDraft"),
    });
    expect(resume).toHaveAttribute("href", `/${TENANT}/requests/new?request=sr-0001`);
    for (const [no, id] of [
      ["SR-26-0002", "sr-0002"],
      ["SR-26-0003", "sr-0003"],
      ["SR-26-0004", "sr-0004"],
    ]) {
      const edit = within(rowOf(no)).getByRole("link", {
        name: t("customers.serviceRequest.action.edit"),
      });
      expect(edit).toHaveAttribute("href", `/${TENANT}/requests/new?request=${id}`);
    }
  });

  it("the list: an APPROVED or REFUSED row has no Edit and no Resume at all", async () => {
    const { client } = makeServer(storedRequest(), ROWS);
    mountAt(client, `/${TENANT}/requests?segment=all`);
    await screen.findByText("SR-26-0005");
    for (const no of ["SR-26-0005", "SR-26-0006"]) {
      const cell = within(rowOf(no));
      expect(cell.queryByRole("link", { name: t("customers.serviceRequest.action.edit") })).toBeNull();
      expect(cell.queryByRole("link", { name: t("customers.serviceRequest.action.resumeDraft") })).toBeNull();
      expect(cell.queryByRole("button", { name: t("customers.serviceRequest.action.edit") })).toBeNull();
    }
  });

  it("pressing Edit on the list OPENS the capture screen (REQ-03) with the request loaded", async () => {
    const { client } = makeServer(storedRequest(), [row(ID, "submitted")]);
    mountAt(client, `/${TENANT}/requests?segment=all`);
    await screen.findByText(`SR-26-${ID.slice(-4)}`);
    fireEvent.click(
      within(rowOf(`SR-26-${ID.slice(-4)}`)).getByRole("link", {
        name: t("customers.serviceRequest.action.edit"),
      }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("where")).toHaveTextContent(`/${TENANT}/requests/new?request=${ID}`),
    );
    expect(document.querySelector('[data-screen="REQ-03"]')).not.toBeNull();
    await loaded();
  });

  it("the request's own page: Edit is there while submitted and leads to the same address", async () => {
    const { client } = makeServer(storedRequest({ state: "submitted" }));
    mountAt(client, `/${TENANT}/requests/${ID}`);
    const edit = await screen.findByRole("link", { name: t("customers.serviceRequest.action.edit") });
    expect(edit).toHaveAttribute("href", `/${TENANT}/requests/new?request=${ID}`);
  });

  it("the request's own page: an APPROVED request has no Edit", async () => {
    const { client } = makeServer(storedRequest({ state: "approved" }));
    mountAt(client, `/${TENANT}/requests/${ID}`);
    await screen.findByRole("heading", { level: 1, name: "Dana Whitfield" });
    expect(screen.queryByRole("link", { name: t("customers.serviceRequest.action.edit") })).toBeNull();
    expect(screen.queryByRole("link", { name: t("customers.serviceRequest.action.resumeDraft") })).toBeNull();
  });

  it("typing the address of an APPROVED request into the bar gets a refusal, not a form", async () => {
    const { calls, client } = makeServer(storedRequest({ state: "approved" }));
    mountAt(client, `/${TENANT}/requests/new?request=${ID}`);
    await screen.findByText(t("customers.serviceRequest.approvedNoEdit"));
    expect(document.getElementById("full_name")).toBeNull();
    expect(patches(calls)).toEqual([]);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// (e) · DEF-CUS-9041 — a SUBMITTED request's property can still be PICKED
// ══════════════════════════════════════════════════════════════════════════
// Every portal application arrives already submitted, so this is the ONLY
// shape a clerk meets it in. The street box used to be read-only here AND the
// one thing that started the register search, so no row could ever be picked
// and the Approve dialog read *Property — Not in Premises* over an address the
// utility holds. What the applicant typed is kept word for word (BR-CUS-070):
// the pick travels, `address_as_given` does not.
describe("(e) a submitted request's property is picked from the register — DEF-CUS-9041", () => {
  it("typing a street searches Premises, a pick and a unit are saved, and the applicant's words are not sent", async () => {
    const { calls, client, stored } = makeServer(
      storedRequest({ address_as_given: "212 Balcones Drive, Austin, TX 78704" }),
    );
    mountAt(
      client,
      `/${TENANT}/requests/new?request=${ID}&step=${captureStepNumber("property")}`,
    );
    await waitFor(() =>
      expect(input("address_as_given")).toHaveValue("212 Balcones Drive, Austin, TX 78704"),
    );
    expect(input("address_as_given")).not.toHaveAttribute("readonly");
    fireEvent.change(input("address_as_given"), { target: { value: "Balcones" } });
    const option = await screen.findByRole("button", { name: "P-00212 · 212 Balcones Drive" });
    expect(
      calls.some((call) => call.method === "GET" && call.path === "/premises/picker"),
    ).toBe(true);
    fireEvent.click(option);
    const unit = (await waitFor(() => {
      const el = document.getElementById("address_unit_as_given");
      expect(el?.tagName).toBe("SELECT");
      return el;
    })) as HTMLSelectElement;
    fireEvent.change(unit, { target: { value: "unit-3" } });
    fireEvent.click(
      screen.getByRole("button", { name: t("customers.serviceRequest.capture.saveChanges") }),
    );
    await waitFor(() => expect(patches(calls)).toHaveLength(1));
    const body = patches(calls)[0].body ?? {};
    expect(body.picked_premises_id).toBe("prem-212");
    expect(body.picked_unit_id).toBe("unit-3");
    // BR-CUS-070 — the server refuses this key on a submitted request.
    expect(body).not.toHaveProperty("address_as_given");
    expect(stored.address_as_given).toBe("212 Balcones Drive, Austin, TX 78704");
  });
});
