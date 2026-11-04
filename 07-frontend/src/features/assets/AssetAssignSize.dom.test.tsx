// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-AST-7660 — Unit detail → Assets → `+ Assign from inventory`
//          opens a panel with a search box and a Service picker and NO
//          connection-size control, so a meter is installed with
//          `size_class` NULL and `BR-RAT-108` cannot price its base charge.
//          The Product Owner's own report: *"the clerk cannot set the
//          connection size, so the size column in the unit's table is blank"*.
// Rules:   BR-AST-500 (the column — NULL is a real answer and is never
//          defaulted) · BR-AST-501 (billing-affecting) · BR-AST-530 (the
//          screens offer the size for METERS) · BR-RAT-108 (service → account
//          type → size class picks the base charge) · BR-TEN-078 (the size
//          list is NOT service-scoped) · DEF-3098 (whether a service BANDS is
//          a ruled fact, never "does it have size rows") · B14 rule 43 (a
//          piece of UI is a COMPONENT) · hard-won law 2 (built is not wired)
// Tests:   this file — TC-S1..S7
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY THIS FILE IS IN `features/assets/` AND MOUNTS A `features/metering/`
// COMPONENT.** The control and the rule are the ASSETS module's
// (`assetsShared.tsx`, `BR-AST-500`); the panel that was missing it is the
// unit tab's. `UnitAssignFromInventory.dom.test.tsx` next door owns that
// panel's OWN cases and is a live sibling's file, so these go here rather than
// into it. The component is exported, so this costs nothing but an import.
//
// ⚠ **THEY ASSERT RENDERED OUTPUT AND THE REQUEST, NEVER A PROP.** A size
// control that existed and was never sent is exactly hard-won law 2's dead UI,
// and `toHaveValue` on a `<select>` would pass over it. Every case below reads
// the DOM the clerk sees, or the body that travels to the server.
//
// RED-FIRST PROOF (r11 step 2d), taken before this lane's change with the
// branch at `db075389b`:
//
//   TC-S1 → Unable to find a label with the text of: /Connection size/
//   TC-S2 → expected false to be true      (nothing asked the server)
//   TC-S3 → Unable to find a label with the text of: /Connection size/
//   TC-S4 → Unable to find a label with the text of: /Connection size/
//   TC-S5 → Unable to find a label with the text of: /Connection size/
//   TC-S7 → Unable to find an element with the text: Choose this meter's
//           connection size.
//
// and after the change, with `required={sizeRequired}` replaced by
// `required={true}`, TC-S4 went RED with *expected element to not be required*
// — the "do not make it blanket-required" half is asserted, not assumed.
//
// ⚠ **TC-S6 IS THE ONE THAT PASSED BEFORE THE CHANGE, AND IT IS SAID HERE
// RATHER THAN LEFT FOR A READER TO NOTICE** (hard-won law 7, habit 2: ask what
// would make a check pass wrongly). It asserts the key is ABSENT, which is
// trivially true of a panel that never sends it. It earns its place only
// AFTER the control exists, where it is the difference between omitting the
// key and posting `size_class: ""` — and `""` would read to the server as
// *clear the size this device already has*. A case that cannot go red at
// birth is not proof of the fix; it is a guard against the next edit.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { AssetRow, UnitRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import i18n from "@/i18n";

import { InventoryFinder } from "@/features/metering/UnitDetailPage";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** ⚠ **REAL CODES, NOT INVENTED ONES** — the same discipline `AssetSizeDoors`
 *  states at its own constant: a fixture that types `5/8` teaches a reader a
 *  vocabulary the product does not have, and it is how `DEF-MET-6926` hid. */
const SIZE_ROWS = [
  { id: "sc-1", code: "W-58", name: 'Water 5/8"', active: true, is_system: true },
  { id: "sc-2", code: "W-2", name: 'Water 2"', active: true, is_system: true },
  { id: "sc-3", code: "W-OLD", name: 'Water 3/4" (retired)', active: false, is_system: true },
];

/**
 * The server's own answer, never derived here (`DEF-3098`). Water and electric
 * BAND; solar is a CAPACITY service and does not.
 *
 * ⚠ **`not_ruled` CARRIES A NAME NO TENANT HOLDS, ON PURPOSE.** Measured on
 * 2026-09-28, the server returns an EMPTY `not_ruled` for every tenant — the
 * one unruled thing is the DIMENSION `thermal_heat_steam`, and a dimension is
 * not a service code. A fixture that put a REAL service there would teach a
 * reader that thermal or battery is unruled, which is two rulings out of date
 * and is exactly the belief that turned the backend's `test_tc_b9` red.
 */
const BANDED = {
  banded: ["electric", "water"],
  not_banded: ["solar"],
  not_ruled: ["a_future_service_nobody_has_ruled"],
};

function unit(services: string[] = ["electric", "water", "solar"]): UnitRow {
  return {
    id: "u-101a",
    unit_no: "U-00101-A",
    premises_id: "p-101",
    premise_no: "P-00101",
    premise_address: "1408 Bluestem Ln",
    label: "Unit A",
    unit_type: "residential",
    floor_label: null,
    square_feet: null,
    rate_plan_id: null,
    plan_effective_from: null,
    plan_locked: false,
    vacant_standby_auto: false,
    is_common_area: false,
    lat: null,
    lng: null,
    point: { lat: null, lng: null, source: "premises" as const },
    active: true,
    services,
    meters: [],
    occupancy: "occupied",
    occupant: "Miller, Sarah",
    account_no: "A-00412",
    status: "active",
    metered_services: [],
    sub_metered: false,
  };
}

/** One shelved meter with NO size — the row this defect is about. */
function spare(overrides: Partial<AssetRow> = {}): AssetRow {
  return {
    id: "inv-5100",
    asset_no: "M-5099",
    serial_no: null,
    type: "meter",
    type_name: "Meter",
    tab: "meters",
    status: "inventory",
    status_name: "Inventory",
    behavior_class: "available",
    meter_type: "ami",
    meter_type_name: "AMI",
    read_method: "ami",
    read_method_name: "AMI",
    multiplier: "1",
    size_class: null,
    size_class_name: null,
    unit: "kgal",
    net_metering: false,
    manufacturer: "Badger Meter",
    model: null,
    install_date: null,
    parent_asset_no: null,
    service_point_id: null,
    assigned_unit_id: null,
    assigned_to: null,
    assigned_address: null,
    assigned: false,
    test_due: false,
    retire_date: null,
    retire_reason: null,
    replaced_by: null,
    actions: ["assign", "edit", "delete"],
    ...overrides,
  };
}

function finderAnswer(rows: AssetRow[]) {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    resolved: { filters: {}, chips: [], unmatched: [] },
  };
}

function paged(rows: unknown[]) {
  return { count: rows.length, next: null, previous: null, results: rows };
}

/**
 * A client that records every URL and body, and answers each read from the
 * same script the real endpoints would. The size catalogue and the banded
 * list are BOTH served, because the panel now asks for both.
 */
function recordingClient(reassign: () => unknown = () => ({ warnings: [] })) {
  const seen: { url: string; body: unknown; method: string }[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      seen.push({
        url,
        method,
        body: init?.body === undefined || init.body === null ? null : JSON.parse(String(init.body)),
      });
      let payload: unknown = {};
      let status = 200;
      if (url.includes("/assets/size-banded-services")) {
        payload = BANDED;
      } else if (url.includes("service_size_classes")) {
        payload = paged(SIZE_ROWS);
      } else if (url.includes("/reassign")) {
        const answer = reassign() as { status?: number; body?: unknown };
        if (answer && typeof answer === "object" && "status" in answer) {
          status = answer.status ?? 200;
          payload = answer.body ?? {};
        } else {
          payload = answer;
        }
      } else {
        payload = finderAnswer([spare()]);
      }
      return new Response(JSON.stringify(payload), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  return { client, seen };
}

function mountFinder(
  client: ReturnType<typeof recordingClient>["client"],
  unitRow: UnitRow = unit(),
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* ⚠ **MOUNTED UNDER THE REAL PATH PATTERN**, never a bare
            `MemoryRouter`: `useParams().tenant` is undefined under one and
            every address the panel builds comes out protocol-relative, which
            reads as a perfectly good string to a `toContain` (hard-won law 2's
            fixture clause). */}
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/units/u-101a?tab=assets`]}>
          <Routes>
            <Route
              path="/:tenant/premises/units/:unitId"
              element={
                <InventoryFinder
                  unit={unitRow}
                  client={client}
                  t={t}
                  writeBlockedReason={null}
                  onAssigned={() => undefined}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

const openPanel = async (user: ReturnType<typeof userEvent.setup>) =>
  user.click(await screen.findByRole("button", { name: "+ Assign from inventory" }));

afterEach(cleanup);

describe("DEF-AST-7660 — the assign-from-inventory form can record a connection size", () => {
  it("TC-S1 · the panel OFFERS a connection size, with the tenant's names and no default", async () => {
    const user = userEvent.setup();
    const { client } = recordingClient();
    mountFinder(client);
    await openPanel(user);

    const picker = (await screen.findByLabelText(/Connection size/)) as HTMLSelectElement;
    // ⚠ **NO DEFAULT.** `BR-AST-500` — NULL is a real answer and is never
    // defaulted, so the leading option is the placeholder.
    expect(picker.value).toBe("");
    // B14 rule 31: the catalogue CODE never reaches the screen — only the
    // tenant's own NAME. And the RETIRED row is not offered, exactly as the
    // add wizard and the edit form filter it.
    expect([...picker.options].map((option) => option.textContent)).toEqual([
      // The placeholder says what a blank MEANS rather than reading as an
      // error — `BR-AST-500`: nobody recorded one, and that is a real answer.
      "Not recorded",
      'Water 5/8"',
      'Water 2"',
    ]);
  });

  it("TC-S2 · it asks the SERVER which services band — it does not infer it", async () => {
    const user = userEvent.setup();
    const { client, seen } = recordingClient();
    mountFinder(client);
    await openPanel(user);

    // ⚠ **THE REQUEST IS THE ASSERTION.** A panel that decided "this tenant
    // has water size classes, so water must band" would render everything
    // below and would be `DEF-3098` for the fifth time.
    await waitFor(() => {
      expect(seen.some((call) => call.url.includes("/assets/size-banded-services"))).toBe(true);
    });
  });

  it("TC-S3 · on a SIZE-BANDED service the field is required", async () => {
    const user = userEvent.setup();
    const { client } = recordingClient();
    mountFinder(client);
    await openPanel(user);
    await user.selectOptions(await screen.findByLabelText("Service"), "water");

    const picker = (await screen.findByLabelText(/Connection size/)) as HTMLSelectElement;
    await waitFor(() => expect(picker).toBeRequired());
  });

  it("TC-S4 · on a service that does NOT band it stays optional, and so does no service", async () => {
    const user = userEvent.setup();
    const { client } = recordingClient();
    mountFinder(client);
    await openPanel(user);

    const picker = (await screen.findByLabelText(/Connection size/)) as HTMLSelectElement;
    // Nothing chosen yet: there is nothing to judge the size against.
    expect(picker).not.toBeRequired();

    // ⚠ **NOT BLANKET-REQUIRED ACROSS EVERY SERVICE.** Solar is a CAPACITY
    // service: its rows are a quantity to SUM and its price does not vary by
    // band, so a required size here would refuse a legitimate install for a
    // fact that does not exist (`DEF-3098`).
    await user.selectOptions(await screen.findByLabelText("Service"), "solar");
    await waitFor(() => expect(picker).not.toBeRequired());
  });

  it("TC-S5 · the chosen size travels in the reassign payload", async () => {
    const user = userEvent.setup();
    const { client, seen } = recordingClient();
    mountFinder(client);
    await openPanel(user);
    await user.selectOptions(await screen.findByLabelText("Service"), "water");
    // `W-2` is the SECOND size, chosen deliberately: picking the first would
    // pass on a picker that silently defaults.
    await user.selectOptions(await screen.findByLabelText(/Connection size/), "W-2");
    await user.click(await screen.findByRole("button", { name: "Assign ✓" }));

    await waitFor(() => {
      const post = seen.find(
        (call) => call.url.includes("/assets/inv-5100/reassign") && call.method === "POST",
      );
      expect(post).toBeDefined();
      expect(post?.body).toMatchObject({
        unit_id: "u-101a",
        record_final_read: false,
        service: "water",
        size_class: "W-2",
      });
    });
  });

  it("TC-S6 · with no size chosen the key is OMITTED, never sent empty", async () => {
    const user = userEvent.setup();
    const { client, seen } = recordingClient();
    mountFinder(client, unit(["solar"]));
    await openPanel(user);
    await user.selectOptions(await screen.findByLabelText("Service"), "solar");
    await user.click(await screen.findByRole("button", { name: "Assign ✓" }));

    await waitFor(() => {
      const post = seen.find(
        (call) => call.url.includes("/assets/inv-5100/reassign") && call.method === "POST",
      );
      expect(post).toBeDefined();
      // ⚠ An empty string is NOT the same message as an absent key: the server
      // branches on truthiness and `""` would read as "clear the one it has".
      expect(Object.keys(post?.body as object)).not.toContain("size_class");
    });
  });

  it("TC-S7 · the SERVER's refusal is what the clerk reads, and the asset did not move", async () => {
    const user = userEvent.setup();
    const { client } = recordingClient(() => ({
      status: 422,
      // ⚠ **THE RATIFIED ENVELOPE, FLAT — `core/errors.py`'s own six keys.**
      // A fixture that nested this under `error:` would fall through
      // `asEnvelope` to the generic *something went wrong* line and the case
      // would pass over a screen that never showed the real refusal.
      body: {
        code: "VAL-001",
        message_key: "assets.size_class_required_for_banded_service",
        params: { service: "water", asset_no: "M-5099" },
        field_errors: [
          {
            field: "size_class",
            code: "VAL-001",
            message_key: "assets.size_class_required_for_banded_service",
            params: { service: "water", asset_no: "M-5099" },
          },
        ],
        br_ref: "BR-AST-500",
        trace_id: "t-1",
      },
    }));
    mountFinder(client);
    await openPanel(user);
    await user.selectOptions(await screen.findByLabelText("Service"), "water");
    await user.click(await screen.findByRole("button", { name: "Assign ✓" }));

    // ⚠ **THE SENTENCE THE SERVER SENT, NOT ONE THIS SCREEN INVENTED.** The
    // browser's `required` mark and the server's refusal are two halves of one
    // rule, and only the server's half is law — a clerk who reaches the refusal
    // some other way (an old tab, a script) must still read the same words.
    expect(await screen.findByText("Choose this meter's connection size.")).toBeInTheDocument();
  });
});
