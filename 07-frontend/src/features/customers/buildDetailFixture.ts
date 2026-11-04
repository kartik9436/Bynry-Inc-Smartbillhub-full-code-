// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 · the fixture the three `BuildDetail*` suites mount
//           the page over. ONE fixture, so three suites cannot come to
//           disagree about what a build looks like.
// Rules:    B14 rule 37 — **every figure here is an ILLUSTRATION and nothing
//           asserts one.** The numbers are deliberately NOT the PNGs': a test
//           that reproduced `B-2026-00042` and `$1,035.00` would be asserting
//           a drawing's examples, which rule 37 forbids outright.
// ───────────────────────────────────────────────────────
import type {
  BuildRecord,
  BuildFacts,
  ScopedWorkOrderList,
  ScopedWorkOrderRow,
} from "@/features/work/workEndpoints";

import type { ConnectionDetail } from "./newConnectEndpoints";

export const TENANT = "brazosbend";
export const BUILD_ID = "01a0b111-2222-7333-8444-555566667777";
export const PREMISES_ID = "01a0c888-9999-7aaa-8bbb-ccccddddeeee";
export const ACCOUNT_ID = "01a0d222-3333-7444-8555-666677778888";
export const UNIT_ID = "01a0e333-4444-7555-8666-777788889999";
export const INVOICE_ID = "01a0e333-4444-7555-8666-7777888800aa";
export const PAYMENT_ID = "01a0e333-4444-7555-8666-7777888800bb";
export const ORDER_ID = "01a0f444-5555-7666-8777-888899990000";
/** A SECOND order of this build, held by a PERSON where `ORDER_ID` is held by
 *  a CREW — the two halves of the one holder the wire serves. */
export const ORDER_ID_2 = "01a0f444-5555-7666-8777-88889999aaaa";
/** An order at the SAME ADDRESS that this build did not raise. It exists so
 *  the Work tab's narrowing can be proved to bite: the shared read answers
 *  every job at the premises and only this build's may be drawn. */
export const OTHER_BUILDS_ORDER_ID = "01a0f444-5555-7666-8777-88889999bbbb";

export function buildDetailFixture(over: Partial<ConnectionDetail> = {}): ConnectionDetail {
  return {
    id: BUILD_ID,
    connection_no: "CON-26-0311",
    state: "partly_activated",
    premises: {
      id: PREMISES_ID,
      premise_no: "PR-0731",
      name: "Cedar Court",
      address: "44 Cedar Court",
    },
    prefill: null,
    unit_summary: null,
    applicant: "Okonkwo, Ada",
    request_no: "SR-26-0104",
    mode: "our_crew",
    started_at: "2026-09-12T10:31:00Z",
    target_activation: "2026-10-15",
    waiting_on: "Fire marshal",
    units: 2,
    orders: { done: 1, total: 2 },
    services: [
      { service: "water", state: "activated", units_energised: 2, units_total: 2, activated_at: null },
      { service: "fire", state: "awaiting", units_energised: 0, units_total: 2, activated_at: null },
    ],
    work_orders: [
      {
        id: ORDER_ID,
        order_no: "WO-26-0309",
        type: "Site inspection",
        service: "water",
        scope: "per_unit",
        unit_label: "1",
        mode: "our_crew",
        state: "completed",
        outcome: "passed",
        is_gate: false,
        blocked_by_order_no: null,
        external_ref: null,
        completed_at: "2026-10-02T09:00:00Z",
        accepted_at: null,
        accepted_by: null,
        field_data: null,
      },
      {
        id: ORDER_ID_2,
        order_no: "WO-26-0310",
        type: "Fire marshal inspection",
        service: "fire",
        scope: "per_premises",
        unit_label: null,
        mode: "our_crew",
        state: "planned",
        outcome: null,
        is_gate: true,
        blocked_by_order_no: null,
        external_ref: null,
        completed_at: null,
        accepted_at: null,
        accepted_by: null,
        field_data: null,
      },
    ],
    unit_rows: [
      {
        id: UNIT_ID,
        label: "1",
        unit_type: "Dwelling",
        services: ["water", "fire"],
        meters: 1,
        plan: "Residential City Plan",
        occupancy: "vacant_service_off",
        account_no: null,
        characteristics: [],
      },
    ],
    assets: [
      {
        id: "01a10555-6666-7777-8888-99990000aaaa",
        asset_no: "M-4471",
        service: "water",
        kind: "meter",
        unit_label: "1",
        size: 'Water 1"',
        multiplier: null,
        read_method: null,
        parent: null,
        status: "active",
      },
    ],
    sub_meter_links: null,
    quote_total: { stored: "612.0000", display: "$612.00" },
    quote_settled_at: null,
    charges: null,
    deposit: null,
    outstanding: [
      {
        id: "01a11666-7777-7888-8999-aaaabbbbcccc",
        title: "Fire marshal not attended",
        detail: null,
        source: "human",
        blocks_creation: false,
      },
    ],
    history: [
      { at: "2026-09-12T10:31:00Z", who: "Dana Whitfield", what: "Build created" },
    ],
    owner_account_no: "AC-26-0088",
    unavailable: [],
    ...over,
  } as ConnectionDetail;
}

const EMPTY_SECTION = { count: 0, page: 1, per: 50, results: [] };

export function buildRecordFixture(over: Partial<BuildRecord> = {}): BuildRecord {
  return {
    id: BUILD_ID,
    connection_no: "CON-26-0311",
    header: {
      owner_name: "Okonkwo, Ada",
      applicant: "Okonkwo, Ada",
      request_no: "SR-26-0104",
      state: "partly_activated",
      waiting_on: "Fire marshal",
      target_activation: "2026-10-15",
      services: ["water", "fire"],
    },
    tiles: {
      units: 2,
      activated: { done: 1, total: 2 },
      service_points: { done: 2, total: 4 },
      work_orders: { done: 1, total: 2 },
      quoted: { stored: "612.0000", display: "$612.00" },
      outstanding: { stored: "112.0000", display: "$112.00" },
    },
    live_state: {
      state: "partly_activated",
      waiting_on: "Fire marshal",
      units_activated: { done: 1, total: 2 },
      service_points_live: { done: 2, total: 4 },
      target_activation: "2026-10-15",
      activated_at: null,
    },
    owner_and_scope: {
      owner_type: "builder_developer",
      units_prefix: null,
      scope: "new_premise",
      owner_or_developer: "Okonkwo, Ada",
      external_system_reference: null,
      mode: "our_crew",
      mode_recorded: "our_crew",
    },
    premise: {
      premise_type: "Apartment block",
      premise_type_code: "apartment",
      address_line: "44 Cedar Court",
      unit_label: null,
      city: "Ottumwa",
      state: "IA",
      postal_code: "58245",
      parcel_or_gis_ref: null,
      external_ref: null,
      routes: [],
      premise_no: "PR-0731",
    },
    where_it_came_from: {
      request_no: "SR-26-0104",
      approved: { by: null, at: null },
      created_at: "2026-09-12T09:58:00Z",
      started_at: "2026-09-12T10:31:00Z",
      fee_outstanding: { stored: null, display: null },
    },
    plan: { services: [], assets: [], sub_meter_links: [] },
    money: {
      invoice_no: "INV-26-0318",
      // `CR-163-BRC10` — the ids an ADDRESS is built from (items 21, 22).
      invoice_id: INVOICE_ID,
      billed_to: "AC-26-0088",
      billed_to_id: ACCOUNT_ID,
      quoted: { stored: "612.0000", display: "$612.00" },
      quote_total_recorded: { stored: "612.0000", display: "$612.00" },
      taken: { stored: "500.0000", display: "$500.00" },
      outstanding: { stored: "112.0000", display: "$112.00" },
      clearing_date: null,
      tender: null,
      reference: null,
      // The wire's own shape: the quantity at STORED scale and the two server
      // display pairs (`CR-163-BRC10` items 18, 19).
      lines: [
        {
          charge_code: "CONN",
          description: "Connection fee",
          quantity: "2.000000",
          unit_price: "45.0000",
          amount: "90.0000",
          each: { stored: "45.0000", display: "45.00" },
          line_total: { stored: "90.0000", display: "90.00" },
          invoice_no: "INV-26-0318",
          invoice_id: INVOICE_ID,
          currency: "USD",
        },
      ],
      bills: [
        {
          invoice_no: "INV-26-0318",
          invoice_id: INVOICE_ID,
          total: { stored: "612.0000", display: "612.00" },
          added: false,
        },
      ],
      // `CR-163-BRC10` item 20 — one row per payment, from payments' own rows.
      payments: [
        {
          id: PAYMENT_ID,
          payment_no: "PY-261002-0084",
          posted_at: "2026-10-02T15:00:00Z",
          method_code: "check",
          method_name: "Check",
          confirmation: "4471",
          type: "payment",
          purpose: "bill",
          status: "cleared",
          amount: { stored: "500.0000", display: "500.00" },
          applied: true,
          currency: "USD",
        },
      ],
      unavailable: [],
    },
    sections: {
      units: { ...EMPTY_SECTION },
      charges: { ...EMPTY_SECTION },
      work_orders: { ...EMPTY_SECTION },
      communication: {
        count: 2,
        page: 1,
        per: 50,
        results: [
          // `CR-163-BRC10` — the wire's own shape since the record reads the
          // QUEUE: one row already queued (When filled, a copy on file) and one
          // with no published wording (item 27).
          {
            code: "build_confirmed",
            channels: ["email"],
            template_code: "CONNECT_CONFIRMED",
            template_available: true,
            sendable: true,
            when: "on_commit",
            state: "queued",
            reason: null,
            sent_at: "2026-10-02T15:30:00Z",
            deliveries: [
              {
                id: "01a0e333-4444-7555-8666-7777888800cc",
                channel: "email",
                copy_no: 0,
                status: "queued",
                queued_at: "2026-10-02T15:30:00Z",
                sent_at: null,
                // ⊕ `DEF-CUS-9195` — the language this copy went in.
                language: "es",
              },
            ],
          },
          {
            code: "quote_and_what_is_owed",
            channels: ["email", "pdf_print"],
            template_code: "new_connect_quote",
            template_available: false,
            sendable: true,
            when: "on_commit",
            state: "not_sent",
            reason: "sent_on_approval",
            sent_at: null,
            deliveries: [],
          },
        ],
      },
      audit: { ...EMPTY_SECTION },
      outstanding: { ...EMPTY_SECTION },
    },
    message_recipients: [
      { code: "owner", name: null, channels: ["email", "pdf_print", "sms"] },
      { code: "co_applicant", name: "Ana Ruiz", channels: ["email"] },
    ],
    unavailable: [],
    ...over,
  } as BuildRecord;
}

function scopedOrder(over: Partial<ScopedWorkOrderRow>): ScopedWorkOrderRow {
  return {
    id: ORDER_ID,
    order_no: "WO-26-0309",
    type: "Site inspection",
    premise: null,
    service: "water",
    state: "completed",
    outcome: "passed",
    mode: "our_crew",
    is_gate: false,
    connection: null,
    account: null,
    raised_at: "2026-09-12T10:31:00Z",
    stands_on: "build",
    scope: "per_unit",
    unit_label: "1",
    external_ref: null,
    completed_at: "2026-10-02T09:00:00Z",
    accepted_at: null,
    accepted_by: null,
    field_data: null,
    technician: null,
    window_start: null,
    window_end: null,
    due_at: null,
    priority: null,
    source: null,
    ...over,
  } as ScopedWorkOrderRow;
}

/**
 * What `GET /premises/{id}/work-orders` answers — **the shared read the build
 * detail's Work tab composes** (`DEF-CUS-7618`).
 *
 * Three rows on purpose, and each one proves a different clause:
 *   * `ORDER_ID` is held by a **CREW**, so the CREW cell names it and the
 *     TECHNICIAN cell states an absence;
 *   * `ORDER_ID_2` is held by a **PERSON**, which is the other way round;
 *   * `OTHER_BUILDS_ORDER_ID` stands at the same address and belongs to
 *     another build, so the narrowing must drop it. Without this row a Work
 *     tab that ignored `onlyOrderIds` entirely would pass every assertion.
 */
export function premisesWorkOrdersFixture(): ScopedWorkOrderList {
  return {
    count: 3,
    // `Paginated`'s four keys, all of them — `assertPaginated` and `G114` read
    // this envelope and a fixture missing two of its keys is a shape the real
    // route never sends.
    next: null,
    previous: null,
    results: [
      scopedOrder({
        technician: { kind: "crew", name: "Meter crew", slug: "meter-crew" },
      }),
      scopedOrder({
        id: ORDER_ID_2,
        order_no: "WO-26-0310",
        type: "Fire marshal inspection",
        service: "fire",
        state: "planned",
        outcome: null,
        unit_label: null,
        scope: "per_premises",
        is_gate: true,
        completed_at: null,
        due_at: "2026-10-10T17:00:00Z",
        technician: { kind: "person", name: "Ray Alvarez", slug: "ray-alvarez" },
      }),
      scopedOrder({
        id: OTHER_BUILDS_ORDER_ID,
        order_no: "WO-26-0411",
        type: "Meter exchange",
        state: "planned",
        outcome: null,
        stands_on: "asset",
        completed_at: null,
        technician: null,
      }),
    ],
  };
}

/** What `GET /premises/{id}/build` answers — the ONE read that carries the
 *  owner account's id, and the page uses it only when it names THIS build. */
export function premisesBuildFixture(over: Partial<BuildFacts> = {}): BuildFacts {
  return {
    id: BUILD_ID,
    connection_no: "CON-26-0311",
    state: "partly_activated",
    mode: "our_crew",
    target_activation: "2026-10-15",
    quote_total: { stored: "612.0000", display: "$612.00" },
    waiting_on: "Fire marshal",
    units: 2,
    orders: { done: 1, total: 2 },
    outstanding: [],
    home: { kind: "account", id: ACCOUNT_ID },
    premises_id: PREMISES_ID,
    ...over,
  };
}
