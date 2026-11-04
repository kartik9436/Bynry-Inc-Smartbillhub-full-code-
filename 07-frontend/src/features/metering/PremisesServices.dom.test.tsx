// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-036 (h) · DEF-756 — *"No screen can set a premises' services. The
//          Add-Premises wizard and the edit modal both omit the field ... every
//          address you create by hand has none."* (PO, 2026-08-26)
// Screens: S16 (guided add, single premise) · PRM-01 list -> edit modal
// Rules:   BR-MET-003 (services_available is a SUBSET of the tenant's enabled
//          services) · B14 rule 9 (multi-select = removable chips + add control)
// ───────────────────────────────────────────────────────
// ⚠ **A TEST THAT PASSES ON SEEDED DATA WOULD PROVE NOTHING HERE.**
// `sample_data.py` and `seed_demo.py` write the same list by hand to
// `premises.services_available` AND to each unit, so the two can only diverge
// in a tenant built through the UI or by import. So nothing below reads a
// fixture: every case DRIVES THE SCREEN with a keyboard and a mouse and then
// asserts THE JSON BODY THE SERVER RECEIVED. A stub that returned seeded
// services would change nothing about what these assert, because what they
// assert is the request the screen produced.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { PremisesRow, PremisesType, TenantServiceRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { PremisesEditModal } from "./PremisesListPage";
import { unitPremisesPickerKey } from "./UnitsListPage";
import EN from "../../i18n/locales/en.json";

const TEST_TENANT = "brazosbend";

/**
 * **THE FIELD'S VISIBLE NAME, AND IT MOVED UNDER THIS FILE (`DEF-MET-4760`).**
 *
 * These four queries read `"Services available"` until 2026-09-10. That string
 * left the English catalogue on **2026-09-09**, in `5ca82a824`, when
 * `metering.premises.col.services` was reworded to the PO's own word — *"Services
 * available = Utility services = drop down - multi select"* (2026-09-08). The
 * rewording was right and the control was untouched; only the name these cases
 * ask for went stale, so three of them went red and **stayed red for a day**
 * with nobody reading them.
 *
 * ⚠ **IT IS A CONSTANT NOW BECAUSE THE STRING WILL MOVE AGAIN.** Four copies of
 * a label is four places to miss; one is one. The catalogue is still the
 * authority — this is what it says today, asserted below so a rewording fails
 * HERE, once, with the reason next to it, instead of failing four times inside
 * cases about something else entirely.
 */
const SERVICES_LABEL = "Utility services";

describe("DEF-MET-4760 — the label these cases query is the label the product draws", () => {
  it("the catalogue still calls the field what this file asks for", () => {
    // Reword `metering.premises.col.services` and THIS fails, naming the
    // constant to change — instead of three cases about services failing on
    // `Unable to find role="combobox" and name "…"`, which reads as a broken
    // control rather than a moved word and is why nobody looked for a day.
    expect((EN as Record<string, string>)["metering.premises.col.services"]).toBe(SERVICES_LABEL);
  });
});

/** What `GET /settings/services` answers for a utility that sells three of the
 *  ten platform services and has Solar switched OFF. Nothing seeds this — the
 *  point of the fixture is that the control must read THIS and not a list in
 *  the code. */
function services(): TenantServiceRow[] {
  const row = (service: string, name: string, enabled: boolean): TenantServiceRow => ({
    service,
    name,
    enabled,
    primary_uom: null,
    alt_uom: null,
    // DEF-2409: `billing_basis` is BR-RAT-081's declaration as re-ruled on
    // 2026-09-02 — one of THREE (metered · share · capacity), never a
    // boolean. `billed_uom: null` means the register's own unit is billed.
    billing_basis: "metered",
    billed_uom: null,
    conversion_factor: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: null,
    active_accounts: null,
  });
  return [
    row("electric", "Electric", true),
    row("water", "Water", true),
    row("gas", "Gas", false),
    row("sewer", "Sewer", true),
    row("solar", "Solar", false),
  ];
}

const TYPES: PremisesType[] = [
  { id: "t1", code: "single_family", name: "Single-family", active: true, is_system: true },
];

interface Sent {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
}

/** The real `ApiClient`, so the body under assertion is the one that goes over
 *  the wire — `JSON.stringify`d by the client itself, not the object a stub
 *  intercepted one layer earlier. */
function recordingClient(sent: Sent[], refuse?: unknown) {
  return createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const body =
        init?.body === undefined || init?.body === null
          ? null
          : (JSON.parse(String(init.body)) as Record<string, unknown>);
      if (method !== "GET") {
        sent.push({ method, url, body });
        if (refuse !== undefined) {
          return new Response(JSON.stringify(refuse), {
            status: 400,
            headers: { "content-type": "application/json" },
          });
        }
      }
      return new Response(JSON.stringify(premisesRow()), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });
}

/** One premises as `GET /premises` serves it. ⚠ `services_available: []` is what
 *  the selector prints for a column holding SQL NULL — `list(row.services_available
 *  or [])` — so this row is BOTH "never asked" and "answered: none" on the wire,
 *  and the edit modal cannot tell them apart. */
function premisesRow(over: Partial<PremisesRow> = {}): PremisesRow {
  return {
    id: "p-318",
    premise_no: "P-00318",
    name: null,
    address_line: "2200 Riverbend Ct",
    city: "Katy",
    state: "TX",
    postal_code: "77494",
    premises_type: "single_family",
    premises_type_name: "Single-family",
    services_available: [],
    owner_manager: null,
    external_ref: null,
    status: "active",
    units: 0,
    ...over,
  } as PremisesRow;
}

function newQueryClient(): QueryClient {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  qc.setQueryData(queryKeys.tenantServices, services());
  qc.setQueryData(["premises", "types"], TYPES);
  qc.setQueryData(unitPremisesPickerKey, {
    count: 0,
    next: null,
    previous: null,
    results: [],
    rollup: { premises: 0, units: 0, vacant: 0, pending_activation: 0 },
  });
  return qc;
}

function mountEdit(sent: Sent[], row: PremisesRow, refuse?: unknown) {
  const qc = newQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises`]}>
          <PremisesEditModal
            row={row}
            types={TYPES}
            client={recordingClient(sent, refuse)}
            onClose={() => undefined}
            onSaved={() => undefined}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

// ⚠ **MOVED 2026-10-09 (`CR-177-BRC10`).** The two S16 cases that stood here
// mounted the old wizard, whose services control opened with EVERY service on
// the address. The PO ruled the opposite on the redesign — the utility's ACTIVE
// services, in one dropdown, **none ticked** (plan rule 4) — so both cases are
// rewritten against the new page in `addPremise/AddPremisePage.dom.test.tsx`:
// only enabled services are offered, none is ticked, and the body the server
// receives carries exactly the services the clerk ticked.

describe("CR-036 (h) — the premises edit modal can SET a premises' services", () => {
  it("sends the changed list on save", async () => {
    const user = userEvent.setup();
    const sent: Sent[] = [];
    mountEdit(sent, premisesRow({ services_available: ["electric"] }));
    await user.selectOptions(screen.getByRole("combobox", { name: SERVICES_LABEL }), "water");
    await user.click(screen.getByRole("button", { name: "Save premise" }));
    await waitFor(() => expect(sent.length).toBeGreaterThan(0));
    expect(sent[0].method).toBe("PATCH");
    expect(sent[0].body?.services_available).toEqual(["electric", "water"]);
  });

  it("removing the last service SENDS the empty list — a deliberate answer", async () => {
    const user = userEvent.setup();
    const sent: Sent[] = [];
    mountEdit(sent, premisesRow({ services_available: ["electric"] }));
    await user.click(screen.getByRole("button", { name: "Remove Electric" }));
    await user.click(screen.getByRole("button", { name: "Save premise" }));
    await waitFor(() => expect(sent.length).toBeGreaterThan(0));
    expect(sent[0].body).toHaveProperty("services_available");
    expect(sent[0].body?.services_available).toEqual([]);
  });

  it("⚠ DOES NOT BACKFILL: an untouched control sends NO services field at all", async () => {
    const user = userEvent.setup();
    const sent: Sent[] = [];
    // The NULL row — served as `[]`, meaning NEVER ASKED. A clerk who only
    // corrects the street name must not convert that into "answered: none".
    mountEdit(sent, premisesRow({ services_available: [] }));
    await user.type(screen.getByLabelText(/Address/i), " Unit 2");
    await user.click(screen.getByRole("button", { name: "Save premise" }));
    await waitFor(() => expect(sent.length).toBeGreaterThan(0));
    expect(sent[0].body).not.toHaveProperty("services_available");
  });

  it("names the service the server refused, under the control that set it", async () => {
    const user = userEvent.setup();
    const sent: Sent[] = [];
    // The tenant switched Solar off between this screen loading and the save.
    mountEdit(sent, premisesRow({ services_available: ["electric"] }), {
      code: "VAL-005",
      message_key: "errors.val-005",
      params: {},
      field_errors: [
        {
          field: "services_available",
          code: "VAL-005",
          message_key: "metering.service_not_enabled",
          params: { service: "solar" },
        },
      ],
    });
    await user.selectOptions(screen.getByRole("combobox", { name: SERVICES_LABEL }), "water");
    await user.click(screen.getByRole("button", { name: "Save premise" }));
    expect(
      await screen.findByText(/solar isn't one of the services this utility bills/i),
    ).toBeInTheDocument();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-MET-003@4ebc614 (EP-MET-01-premises-units.md, git hash-object,
//         short) + CR-036 (h) scope table, 12-governance/11-change-requests.md
//         (verbatim) + DEF-756, 12-governance/10-defect-log.csv
// screens: S16 (A1) · PRM-01 / PRM-02 (r10)
// generated: 2026-08-26 by lane PREMSVC (CR-036 (h) / DEF-756)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: vitest src/features/metering/PremisesServices.dom.test.tsx 6 passed .
//        tsc --noEmit exit 0 · eslint --max-warnings 0 exit 0
// exceptions:
//   E4 **PROVEN RED BEFORE TRUSTED GREEN (hard-won law 7), five of six on the
//      UNFIXED tree**: `Unable to find a label with the text of: Services
//      available` (x3, the wizard step and the edit modal) and `Unable to find an
//      accessible element with the role "button" and name "Remove Sewer" /
//      "Remove Electric"` (x2). The SIXTH — the no-backfill case — passed
//      trivially there, because a screen with no services control sends no
//      services field; it was proved separately by making the edit modal send
//      `services_available` unconditionally: `expected { ...(9) } to not have
//      property "services_available"`.
//   E4 the "never a hardcoded list" clause was proved the same way — dropping the
//      `.enabled` filter in `enabledServiceRows` turns two cases red:
//      `expected 'Every service you sell is on this add...' not to contain 'Gas'`
//      and `expected [ 'electric', 'water', 'gas', 'solar' ] to deeply equal
//      [ 'electric', 'water' ]`.
//   E3 no case reads seeded data, and the wizard case is built so it CANNOT be
//      satisfied by any: `seed_demo.py` writes `["electric", "water"]` to every
//      seeded premises and unit, so the expectation here is `["electric",
//      "sewer"]` — a pair no seeder in this repo writes.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
