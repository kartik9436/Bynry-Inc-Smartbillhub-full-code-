// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   PO reports 2026-09-23 on `New request` (REQ-03) — lane REQ-FIX.
//           `DEF-CUS-6408` (billing address as a US address, optional) ·
//           `DEF-CUS-6409` (requested start shown, sent and read back) ·
//           `DEF-CUS-6410` (Capture another → a blank step 1) ·
//           `DEF-CUS-6411` (the fees as a table) · `DEF-CUS-6412` (money with
//           its currency) · `DEF-CUS-6413` (labels, not codes) · `DEF-CUS-6415`
//           (`Waive` off the tender list) · `DEF-CUS-6418` (the acknowledgement
//           panel reads the request's own state)
// Harness:  mounted under the REAL route pattern `/:tenant/requests/new`, so
//           `useTenantPath` builds `/brazosbend/…` and not `//…` — CLAUDE.md
//           hard-won law 2's fixture clause. The server is a fake that keeps ONE
//           request and answers the routes the wizard calls, so a flow from
//           step 1 to the confirmation and back is driven for real.
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
  capturePayload,
  emptyCaptureForm,
  serviceStart,
  serviceStartsPayload,
} from "./ServiceRequestCapturePage";
import { FEE_METHODS } from "./serviceRequestEndpoints";
import type { ServiceRequestFeeLine } from "./serviceRequestEndpoints";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

// ══════════════════════════════════════════════════════════════════════════
// 1 · PURE — what the payload carries
// ══════════════════════════════════════════════════════════════════════════

describe("DEF-CUS-6408 · the billing address travels STRUCTURED, and nothing is required", () => {
  it("unticked, the five parts are sent as their own fields — never one blob", () => {
    const payload = capturePayload({
      ...emptyCaptureForm(),
      billing_address_same: false,
      billing_address: {
        line1: " PO Box 4471 ",
        line2: "Suite 200",
        city: "Round Rock",
        state: "TX",
        postal_code: "78664-1234",
      },
    });
    // ⊕ Lane CF-1 (2026-10-18) — sent as the MAILING address, the one name
    // for where the bill goes (the server mirrors it into `billing_*`).
    expect(payload).toMatchObject({
      mailing_same: false,
      mailing_line1: "PO Box 4471",
      mailing_line2: "Suite 200",
      mailing_city: "Round Rock",
      mailing_state: "TX",
      mailing_postal_code: "78664-1234",
    });
    // The one-box field is NOT sent: a draft opened from the list keeps the
    // words a clerk typed there before 2026-09-23.
    expect(payload).not.toHaveProperty("billing_address_as_given");
  });

  it("ticked, every part goes as an empty string — a stale part cannot survive the tick", () => {
    const payload = capturePayload({
      ...emptyCaptureForm(),
      billing_address_same: true,
      billing_address: { line1: "PO Box 1", line2: "", city: "Katy", state: "TX", postal_code: "" },
    });
    expect(payload.mailing_same).toBe(true);
    expect(payload.mailing_line1).toBe("");
    expect(payload.mailing_city).toBe("");
    expect(payload.mailing_state).toBe("");
  });
});

describe("DEF-CUS-6409 · a service's start is the job date unless the clerk says otherwise", () => {
  const base = {
    ...emptyCaptureForm(),
    services: ["water", "sewer", "trash"],
    requested_start: "2026-10-15",
  };

  it("a service nobody retyped carries the job's Connection date — it used to carry NULL", () => {
    expect(serviceStartsPayload({ ...base, service_starts: { sewer: "2026-11-01" } })).toEqual([
      { code: "water", requested_start: "2026-10-15" },
      { code: "sewer", requested_start: "2026-11-01" },
      { code: "trash", requested_start: "2026-10-15" },
    ]);
  });

  it("a box the clerk deliberately EMPTIED is still 'not given' — null", () => {
    expect(serviceStart({ ...base, service_starts: { water: "" } }, "water")).toBeNull();
  });

  it("no job date and no own date is null — nothing is invented", () => {
    expect(serviceStart({ ...base, requested_start: "" }, "water")).toBeNull();
  });
});

describe("DEF-CUS-6415 · `Waive` is not a tender", () => {
  it("the payment methods are card, cash and cheque — waiving is a per-line act", () => {
    expect([...FEE_METHODS]).toEqual(["card", "cash", "cheque"]);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 2 · THE FAKE SERVER — one request, the routes the wizard calls
// ══════════════════════════════════════════════════════════════════════════

const CHARGES = [
  {
    id: "chg-1",
    code: "CC-REQFEE",
    name: "Application processing fee",
    charge_type: "one_time",
    service: null,
    amount_rule: "flat",
    amount: "25.000000",
    percent: null,
    min_amount: null,
    max_amount: null,
    amount_display: "25.00",
    percent_display: null,
    min_amount_display: null,
    max_amount_display: null,
    gl_account_id: "gl-4600",
    status: "active",
  },
  {
    id: "chg-2",
    code: "CONN",
    name: "Connection fee",
    charge_type: "one_time",
    service: null,
    amount_rule: "flat",
    amount: "60.000000",
    percent: null,
    min_amount: null,
    max_amount: null,
    amount_display: "60.00",
    percent_display: null,
    min_amount_display: null,
    max_amount_display: null,
    gl_account_id: "gl-4610",
    status: "active",
  },
];

function money(amount: string, currency: string | null = "USD") {
  const [whole, frac = "0000"] = amount.split(".");
  return { amount, display: `${whole}.${frac.slice(0, 2)}`, currency };
}

/** Sums four-place decimal STRINGS exactly, as integers of ten-thousandths —
 *  the fake server's arithmetic, standing in for the real server's `Decimal`. */
function sum4(values: string[]): string {
  const total = values.reduce((acc, v) => {
    const [w, f = ""] = v.split(".");
    return acc + BigInt(w) * 10000n + BigInt((f + "0000").slice(0, 4));
  }, 0n);
  const w = total / 10000n;
  const f = (total % 10000n).toString().padStart(4, "0");
  return `${w}.${f}`;
}

interface Fake {
  calls: { method: string; path: string; body: unknown }[];
  lines: ServiceRequestFeeLine[];
  state: string;
  services: { code: string; requested_start: string | null }[];
  requestNo: string;
  /** `DEF-CUS-10041` — what `POST .../fee-collection` was handed, if anything. */
  collected: { amount: string; method: string; receipt_no: string } | null;
}

function makeServer(): { fake: Fake; client: ReturnType<typeof createApiClient> } {
  const fake: Fake = {
    calls: [],
    lines: [],
    state: "draft",
    services: [],
    requestNo: "SR-26-0016",
    collected: null,
  };
  let form: Record<string, unknown> = {};

  function feesTab() {
    const live = fake.lines.filter((line) => !line.waived);
    const quoted = sum4(live.map((line) => line.amount.amount));
    const currency = fake.lines.length === 0 ? null : "USD";
    return {
      lines: fake.lines,
      outstanding_lines: live.length,
      quoted: money(fake.lines.length === 0 ? "0.0000" : quoted, currency),
      settled: money("0.0000", currency),
      collected: money(fake.collected === null ? "0.0000" : fake.collected.amount, currency),
      outstanding: money(
        fake.lines.length === 0 || fake.collected !== null ? "0.0000" : quoted,
        currency,
      ),
      shortfall_is_open_balance: live.length > 0,
      receipt_no: fake.collected === null ? null : fake.collected.receipt_no,
      collected_at: null,
      quoted_at_collection: null,
      fee_timing: form.fee_timing ?? null,
      fee_due_by: null,
      fee_method: fake.collected?.method ?? ((form.fee_method as string | undefined) || null),
      posts_to_ledger: false,
      connection_quote: { raised: false, reason: "raised_after_review" },
    };
  }

  function detail() {
    return {
      header: {
        id: "sr-1",
        request_no: fake.requestNo,
        number_absence: null,
        state: fake.state,
        queue: null,
        classification: "not_yet_classified",
        applicant: form.applicant_name ?? null,
        address_as_given: form.address_as_given ?? null,
        address_unit_as_given: null,
        premise_locality: null,
        lookup_found: null,
        received_at: "2026-09-23T09:00:00Z",
        received_by: "user-1",
        channel: "walk_in",
        waiting_on: null,
        waiting_since: null,
        requested_start: form.requested_start ?? null,
      },
      actions: { available: [], can_approve: false, approve_blocked_by: [], can_park: true },
      applicant: {
        name: form.applicant_name ?? null,
        phone: null,
        email: form.applicant_email ?? null,
        language: null,
        person_or_company: "person",
        co_applicant: { name: null, email: null, phone: null },
        identifier: {
          ssn_last4: null,
          ssn_present: false,
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
        address_as_given: form.address_as_given ?? null,
        address_unit_as_given: null,
        address_city_as_given: null,
        address_state_as_given: null,
        address_postal_code_as_given: null,
        units_on_property: null,
        billing_address_same: form.billing_address_same ?? true,
        billing_address_as_given: null,
        billing_line1_as_given: form.billing_line1_as_given || null,
        billing_line2_as_given: form.billing_line2_as_given || null,
        billing_city_as_given: form.billing_city_as_given || null,
        billing_state_as_given: form.billing_state_as_given || null,
        billing_postal_code_as_given: form.billing_postal_code_as_given || null,
        resolved_premises_id: null,
        resolved_unit_id: null,
        resolved_premises_no: null,
        resolved_unit_no: null,
        resolved_premise_address: null,
        premise_locality: null,
        resolved_match: null,
        resolution_kind: "no_premise",
        lookup_found: null,
        plot_or_parcel: null,
        what_is_being_built: null,
        property_type: null,
        no_premise_flag: true,
        services: fake.services.map((row) => ({ ...row, available: null })),
        requested_start_agreement: { count: fake.services.length, agreed: null, unset: 0 },
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
      fees: feesTab(),
      decision: {
        what_they_said: null,
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
        acknowledgement:
          fake.state === "submitted"
            ? { state: "queued", reason: null, ref: "OM-1", sent: false, fee_statement: null }
            : { state: null, reason: null, ref: null, sent: false, fee_statement: null },
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

  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "http://x");
      const path = url.pathname.replace(/^\/api\/brazosbend/, "");
      const method = (init?.method ?? "GET").toUpperCase();
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      fake.calls.push({ method, path, body });
      if (method === "GET") {
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
        if (path === "/charges") {
          return json({ count: CHARGES.length, next: null, previous: null, results: CHARGES });
        }
        if (path === "/payments") {
          // The utility's own list, as Settings seeds it (`DEF-CUS-10041`).
          return json({
            count: 0,
            next: null,
            previous: null,
            results: [],
            totals: {},
            methods: ["ach", "card", "check", "cash", "lockbox", "wire", "money_order"].map((code) => ({
              id: `m-${code}`,
              code,
              name: code,
            })),
          });
        }
        if (path === "/payments/reason-codes") {
          return json({ reasons: [{ code: "HARDSHIP", name: "Hardship" }], count: 1 });
        }
        if (path === "/service-requests/sr-1") {
          return json(detail());
        }
        return json({ count: 0, next: null, previous: null, results: [] });
      }
      if (method === "POST" && path === "/service-requests") {
        form = { ...form, ...body };
        return json(detail(), 201);
      }
      if (method === "PATCH" && path === "/service-requests/sr-1") {
        form = { ...form, ...body };
        return json(detail());
      }
      if (method === "POST" && path === "/service-requests/sr-1/services") {
        fake.services = (body.services as { code: string; requested_start: string | null }[]).map(
          (row) => ({ code: row.code, requested_start: row.requested_start }),
        );
        return json(detail());
      }
      if (method === "POST" && path === "/service-requests/sr-1/fees") {
        const unit = String(body.unit_amount);
        const line: ServiceRequestFeeLine = {
          id: `fee-${fake.lines.length + 1}`,
          line_no: fake.lines.length + 1,
          charge_code: body.charge_code,
          description: body.description,
          basis: body.basis ?? null,
          quantity: "1.0000",
          unit_amount: money(sum4([unit])),
          amount: money(sum4([unit])),
          waived: false,
          waive_reason: null,
          settled_at: null,
          invoice_ref: null,
        };
        fake.lines = [...fake.lines, line];
        return json(feesTab());
      }
      const fee = path.match(/^\/service-requests\/sr-1\/fees\/([^/]+)(\/waive)?$/);
      if (fee !== null && method === "DELETE") {
        fake.lines = fake.lines.filter((line) => line.id !== fee[1]);
        return json(feesTab());
      }
      if (fee !== null && method === "POST" && fee[2] === "/waive") {
        fake.lines = fake.lines.map((line) =>
          line.id === fee[1] ? { ...line, waived: true, waive_reason: body.reason } : line,
        );
        return json(feesTab());
      }
      if (method === "POST" && path === "/service-requests/sr-1/fee-collection") {
        const taken = body as { amount: string; method: string; receipt_no: string };
        fake.collected = { amount: taken.amount, method: taken.method, receipt_no: taken.receipt_no };
        return json(feesTab());
      }
      if (method === "POST" && path === "/service-requests/sr-1/submit") {
        fake.state = "submitted";
        return json({
          request: {},
          acknowledgement: { state: "queued" },
          idempotent_replay: false,
        });
      }
      return json(detail());
    },
  });
  return { fake, client };
}

function Where() {
  const location = useLocation();
  return <output data-testid="where">{`${location.pathname}${location.search}`}</output>;
}

function mount(client: ReturnType<typeof createApiClient>, search = "") {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[`/brazosbend/requests/new${search}`]}>
        <Routes>
          <Route
            path="/:tenant/requests/new"
            element={
              <>
                <ServiceRequestCapturePage client={client} />
                <Where />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function pressContinue(): Promise<void> {
  fireEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
}

async function stepCaption(step: number): Promise<void> {
  await screen.findByText(new RegExp(`Step ${step} of 4`));
}

/** Step 1 with a name (so a draft exists) and a category, then step 2 with a
 *  street — leaving the wizard on step 2, THE PROPERTY.
 *
 *  ⚠ **THE ROUTE MOVED ON 2026-09-29 AND THE WALK MOVED WITH IT.** The
 *  category was step 2's and is step 1's; the address was step 3's and is
 *  step 2's; the services and the fees were steps 2 and 5 and are both step 3.
 *  Nothing this walk ASSERTS has changed. */
async function throughToProperty(): Promise<void> {
  fireEvent.change(
    await screen.findByLabelText(new RegExp(t("customers.serviceRequest.capture.fullName"))),
    {
      target: { value: "Rivera, Ana" },
    },
  );
  // ⊕ Lane CF-1 (2026-10-18) — step 1 is the shared customer form: its
  // *Category* is `account_type`, and Move-in's rules ask a person's phone.
  await waitFor(() =>
    expect(document.querySelector('#account_type option[value="residential"]')).not.toBeNull(),
  );
  fireEvent.change(document.getElementById("account_type") as HTMLSelectElement, {
    target: { value: "residential" },
  });
  fireEvent.change(document.getElementById("phone") as HTMLInputElement, {
    target: { value: "(512) 555-0100" },
  });
  await pressContinue();
  await stepCaption(2);
  fireEvent.change(
    screen.getByLabelText(new RegExp(t("customers.serviceRequest.capture.streetOrPremise"))),
    {
      target: { value: "212 Balcones Drive" },
    },
  );
}

/** Step 3 — two services THROUGH THE TABLE ARRAY, and the job date the server
 *  defaulted. `+ Service` makes a row and its chooser fills it, which is the
 *  whole of the redesign's *adding a row IS adding a service* (REQ-03 task 8). */
async function pickTwoServices(): Promise<void> {
  for (const code of ["water", "sewer"]) {
    fireEvent.click(
      await waitFor(() => {
        const node = document.querySelector("[data-add-service]");
        if (node === null) throw new Error("no + Service yet");
        return node as HTMLElement;
      }),
    );
    const rows = [
      ...document.querySelectorAll("[data-editable-table='request-services'] tbody tr"),
    ];
    const last = rows[rows.length - 1] as HTMLElement;
    fireEvent.change(last.querySelector("select") as HTMLSelectElement, {
      target: { value: code },
    });
  }
  // The job date opens on the server's 15-working-days default.
  await waitFor(() =>
    expect((document.getElementById("requested_start") as HTMLInputElement).value).toBe(
      "2026-10-15",
    ),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// 3 · THE FLOW, UNDER THE REAL ROUTE
// ══════════════════════════════════════════════════════════════════════════

describe("REQ-03 · the PO's 2026-09-23 report, driven end to end", () => {
  it("DEF-CUS-6408 · the mailing address is a US address, none of it required, and its parts are saved", async () => {
    // ⊕ **AMENDED 2026-10-18 (lane CF-1).** The block moved to STEP 1 with the
    // rest of the shared customer form (drawing set `customer-forms-2026-10-18`,
    // image 03) and is sent as `mailing_*`. What this case is about is
    // untouched: none of the five is required, a mistyped ZIP holds the step,
    // and all five parts reach the server separately.
    const { fake, client } = makeServer();
    mount(client);
    fireEvent.change(
      await screen.findByLabelText(new RegExp(t("customers.serviceRequest.capture.fullName"))),
      { target: { value: "Rivera, Ana" } },
    );
    await waitFor(() =>
      expect(document.querySelector('#account_type option[value="residential"]')).not.toBeNull(),
    );
    fireEvent.change(document.getElementById("account_type") as HTMLSelectElement, {
      target: { value: "residential" },
    });
    fireEvent.change(document.getElementById("phone") as HTMLInputElement, {
      target: { value: "(512) 555-0100" },
    });

    expect(document.getElementById("mailing_line1")).toBeNull();
    fireEvent.click(screen.getByLabelText(t("customers.account.field.mailingSame")));
    for (const id of ["mailing_line1", "mailing_line2", "mailing_city", "mailing_state", "mailing_postal_code"]) {
      const input = document.getElementById(id) as HTMLInputElement;
      expect(input).toBeEnabled();
      expect(input).not.toHaveAttribute("aria-required");
    }
    fireEvent.change(document.getElementById("mailing_line1") as HTMLInputElement, {
      target: { value: "PO Box 4471" },
    });
    fireEvent.change(document.getElementById("mailing_line2") as HTMLInputElement, {
      target: { value: "Suite 200" },
    });
    fireEvent.change(document.getElementById("mailing_city") as HTMLInputElement, {
      target: { value: "Round Rock" },
    });
    fireEvent.change(document.getElementById("mailing_state") as HTMLInputElement, {
      target: { value: "Tex" },
    });
    fireEvent.click(document.getElementById("mailing_state-opt-TX") as HTMLElement);

    // A mistyped ZIP is caught on the field and holds the step…
    fireEvent.change(document.getElementById("mailing_postal_code") as HTMLInputElement, {
      target: { value: "7866" },
    });
    expect(document.getElementById("mailing_postal_code")).toHaveAttribute("aria-invalid", "true");
    await pressContinue();
    expect(screen.getByText(/Step 1 of 4/)).toBeInTheDocument();

    // …and a well-formed one lets it go, carrying five separate fields.
    fireEvent.change(document.getElementById("mailing_postal_code") as HTMLInputElement, {
      target: { value: "78664-1234" },
    });
    await pressContinue();
    await stepCaption(2);
    await waitFor(() => {
      // The draft's own create (step 1's first save) or its PATCH — not the
      // side calls (category, services, resolve) that follow it.
      const saved = [...fake.calls]
        .reverse()
        .find(
          (call) =>
            (call.method === "POST" && call.path === "/service-requests") || call.method === "PATCH",
        );
      expect(saved?.body).toMatchObject({
        mailing_same: false,
        mailing_line1: "PO Box 4471",
        mailing_line2: "Suite 200",
        mailing_city: "Round Rock",
        mailing_state: "TX",
        mailing_postal_code: "78664-1234",
      });
      expect(saved?.body).not.toHaveProperty("billing_address_as_given");
    });
  }, 30_000);

  it("DEF-CUS-6409 · the date step 3 SHOWS is the date POSTed and the date step 4 READS", async () => {
    const { fake, client } = makeServer();
    mount(client);
    await throughToProperty();
    await pressContinue(); // → 3
    await stepCaption(3);
    await pickTwoServices();
    await pressContinue(); // → 4
    await stepCaption(4);

    // What the server was sent: the job date, for both services — NOT null.
    await waitFor(() =>
      expect(fake.services).toEqual([
        { code: "water", requested_start: "2026-10-15" },
        { code: "sewer", requested_start: "2026-10-15" },
      ]),
    );
    // What the review prints in the REQUESTED START column: the date, not `—`.
    const table = document.querySelector(
      "[data-editable-table='review-services']",
    ) as HTMLElement;
    const starts = within(table)
      .getAllByRole("row")
      .slice(1)
      .map((row) => (row.querySelectorAll("td")[1] as HTMLElement).textContent ?? "");
    expect(starts).toHaveLength(2);
    for (const cell of starts) {
      expect(cell.trim()).not.toBe("—");
      expect(cell).toMatch(/15/);
    }
  }, 30_000);

  it("DEF-CUS-6411 · step 3 is a fee table: pick → a row, remove, waive with a reason, a server Total", async () => {
    const { fake, client } = makeServer();
    mount(client);
    await throughToProperty();
    await pressContinue();
    await stepCaption(3);
    await pickTwoServices();

    // Empty, the table says so — and its add row is already there.
    await waitFor(() =>
      expect(
        document.querySelector("[data-editable-table='application-fees'] [data-editable-empty]"),
      ).not.toBeNull(),
    );
    // `+ Add a fee ▾` — the pick IS the add.
    const pick = async (code: string) => {
      // **`+ Fee` MAKES A ROW AND ITS CHOOSER FILLS IT** — REQ-03 task 9. The
      // separate *Choose a fee…* box is gone: adding a row IS adding a fee.
      fireEvent.click(document.querySelector("[data-add-fee]") as HTMLElement);
      const box = await waitFor(() => {
        const node = document.querySelector(
          "[data-editable-table='application-fees'] tbody select",
        ) as HTMLSelectElement | null;
        if (node === null) throw new Error("no chooser in the new row");
        return node;
      });
      fireEvent.change(box, { target: { value: code } });
    };
    await pick("CC-REQFEE");
    await waitFor(() => expect(fake.lines).toHaveLength(1));
    await pick("CONN");
    await waitFor(() => expect(fake.lines).toHaveLength(2));
    const table = await waitFor(() => {
      const node = document.querySelector("[data-editable-table='application-fees']");
      if (node === null) throw new Error("no fee table");
      return node as HTMLElement;
    });
    // `Code` is not a column; these are, in this order.
    const headers = Array.from(table.querySelectorAll("thead th"))
      .map((th) => th.textContent ?? "")
      .filter((text) => text.trim() !== "");
    expect(headers).toEqual([
      t("customers.serviceRequest.fees.col.fee"),
      t("customers.serviceRequest.fees.col.chargedPer"),
      t("customers.serviceRequest.fees.col.qty"),
      t("customers.serviceRequest.fees.col.unitPrice"),
      t("customers.serviceRequest.fees.col.amount"),
    ]);
    expect(headers).not.toContain(t("customers.serviceRequest.fees.col.waive"));

    const post = fake.calls.find((call) => call.method === "POST" && call.path.endsWith("/fees"));
    expect(post?.body).toMatchObject({
      charge_code: "CC-REQFEE",
      basis: "per request",
      quantity: "1",
    });

    // The Total is the SERVER's Decimal sum — $85.00 — printed with its currency.
    await waitFor(() =>
      expect(
        document.querySelector("[data-editable-table='application-fees'] [data-fee-total]"),
      ).toHaveAttribute("data-fee-total", "85.0000"),
    );
    expect(
      (
        document.querySelector(
          "[data-editable-table='application-fees'] [data-editable-footer]",
        ) as HTMLElement
      ).textContent,
    ).toMatch(/\$85\.00/);

    // Remove CONN — a DELETE, and the table follows the server.
    fireEvent.click(
      screen.getByLabelText(
        `${t("customers.serviceRequest.fees.remove")} — ${t("customers.serviceRequest.fees.col.fee")} 2`,
      ),
    );
    await waitFor(() => expect(fake.lines.map((line) => line.charge_code)).toEqual(["CC-REQFEE"]));
    expect(
      fake.calls.some((call) => call.method === "DELETE" && call.path.endsWith("/fees/fee-2")),
    ).toBe(true);

    // ⛔ **THE WAIVE TICK LEFT THIS SCREEN WITH ITS COLUMN — REQ-03 task 9.**
    // `03-service-1440.png` draws six columns and a waive is not one of them.
    // There is no control here to fire, and the capability is not lost: the
    // request's own Fees panel opens `RequestFeeHandoverModal` with the
    // tenant's reasons. This asserts the ABSENCE rather than leaving the
    // removal invisible to every check.
    expect(document.getElementById("fee-waive-fee-1")).toBeNull();

    // The tender list no longer offers `Waive` — and since `DEF-CUS-10041` it
    // is the UTILITY's list behind *Pay now*, Lockbox left out (it arrives in
    // the bank's file, never across a counter).
    fireEvent.click(screen.getByRole("radio", { name: t("customers.serviceRequest.pay.now") }));
    const method = await waitFor(() => {
      const node = document.getElementById("fee_method") as HTMLSelectElement | null;
      if (node === null || node.options.length < 2) throw new Error("methods not loaded");
      return node;
    });
    const offered = Array.from(method.options)
      .map((option) => option.value)
      .filter(Boolean);
    expect(offered).toEqual(["ach", "card", "check", "cash", "wire", "money_order"]);
  }, 30_000);

  it("DEF-CUS-6410 · Capture another lands on a BLANK step 1 with no draft carried over", async () => {
    const { fake, client } = makeServer();
    mount(client);
    await throughToProperty();
    await pressContinue();
    await stepCaption(3);
    await pickTwoServices();
    await pressContinue();
    await stepCaption(4);
    fireEvent.change(document.getElementById("fee_method") ?? document.createElement("select"), {
      target: { value: "cash" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: t("customers.serviceRequest.capture.submit") }),
    );
    await screen.findByText(fake.requestNo);
    expect(document.querySelector("[data-screen='REQ-03.sent']")).not.toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: t("customers.serviceRequest.sent.captureAnother") }),
    );

    await stepCaption(1);
    expect(document.querySelector("[data-screen='REQ-03.sent']")).toBeNull();
    expect(screen.getByTestId("where").textContent).toBe("/brazosbend/requests/new");
    const name = screen.getByLabelText(
      new RegExp(t("customers.serviceRequest.capture.fullName")),
    ) as HTMLInputElement;
    expect(name.value).toBe("");
    // No number is shown for a request that does not exist yet.
    expect(screen.queryByText(fake.requestNo)).toBeNull();
  }, 30_000);

  it("REQ-03.sent · money carries its currency, the tender is its label, the acknowledgement is the request's own", async () => {
    const { fake, client } = makeServer();
    mount(client);
    await throughToProperty();
    await pressContinue();
    await stepCaption(3);
    await pickTwoServices();
    // **THE SECOND COPY OF THE OLD PICKER, AND IT IS WHY THIS FAILED ONCE.**
    // `pick()` above was moved to `+ Fee` and this inline twin was not; the
    // case then waited on an `application_fee_code` box that no longer exists
    // and timed out on *"picker not ready"*. Found by reading the one red in a
    // run of 141 rather than by any gate (hard-won law 7, habit 1).
    fireEvent.click(document.querySelector("[data-add-fee]") as HTMLElement);
    const box = await waitFor(() => {
      const node = document.querySelector(
        "[data-editable-table='application-fees'] tbody select",
      ) as HTMLSelectElement | null;
      if (node === null) throw new Error("no chooser in the new row");
      return node;
    });
    fireEvent.change(box, { target: { value: "CC-REQFEE" } });
    await waitFor(() => expect(fake.lines).toHaveLength(1));
    // `DEF-CUS-10041` — Pay now, Cash: $30.00 handed over on a $25.00 fee shows
    // $5.00 change, and the WHOLE fee is what is taken at submit.
    fireEvent.click(screen.getByRole("radio", { name: t("customers.serviceRequest.pay.now") }));
    const tender = await waitFor(() => {
      const node = document.getElementById("fee_method") as HTMLSelectElement | null;
      if (node === null || node.options.length < 2) throw new Error("methods not loaded");
      return node;
    });
    fireEvent.change(tender, { target: { value: "cash" } });
    fireEvent.change(document.getElementById("cash_received") as HTMLInputElement, {
      target: { value: "30.00" },
    });
    expect((document.getElementById("cash_change") as HTMLInputElement).value).toBe("$5.00");
    fireEvent.change(document.getElementById("fee_receipt_no") as HTMLInputElement, {
      target: { value: "RCP-26-4471" },
    });
    await pressContinue();
    await stepCaption(4);
    fireEvent.click(
      screen.getByRole("button", { name: t("customers.serviceRequest.capture.submit") }),
    );
    const screenSent = await waitFor(() => {
      const node = document.querySelector("[data-screen='REQ-03.sent']");
      if (node === null) throw new Error("not sent yet");
      return node as HTMLElement;
    });
    const text = screenSent.textContent ?? "";
    // Taken in full at submit: `$25.00 collected of $25.00 quoted`.
    expect(fake.collected).toEqual({ amount: "25.0000", method: "cash", receipt_no: "RCP-26-4471" });
    expect(text).toMatch(/\$25\.00 collected of \$25\.00 quoted/);
    expect(text).not.toMatch(/(^|[^$\d])25\.00 collected of/);
    // HOW IT WAS PAID reads the label.
    expect(screenSent.querySelector("[data-sent-method]")?.textContent).toBe(
      t("customers.serviceRequest.feeMethod.cash"),
    );
    // The acknowledgement reads the REQUEST's state — queued — and never the
    // stale *"none is waiting to be sent"*.
    expect(screenSent.querySelector("[data-ack-state]")?.getAttribute("data-ack-state")).toBe(
      "queued",
    );
    expect(text).toContain(t("customers.serviceRequest.sent.ackQueued"));
    expect(text).not.toMatch(/none is waiting/);
    // The fee lines are the same table, read-only.
    const sentTable = screenSent.querySelector("[data-editable-table='sent-fees']") as HTMLElement;
    expect(sentTable).not.toBeNull();
    expect(sentTable.querySelector("[data-remove-row]")).toBeNull();
  }, 30_000);
});
