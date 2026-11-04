// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-MET-5861 (`On since` rendered `install_date`, which the assign
//          never sets — a dash on every meter assigned from stock) ·
//          DEF-MET-5862 (`Last read` rendered `consumption`, which is the
//          USAGE since the previous read — so a FIRST read, which has no
//          previous value, showed a bare date over a reading that exists)
// Screens: PRM-03 Assets tab (S15 unit detail)
// Rules:   BR-MET-106 / DEF-079 (an unread register is ABSENT, never a zero) ·
//          BR-MET-028 (an estimate has a usage and NO reading) ·
//          BR-MET-144 + CLAUDE.md hard rule 3 (a quantity displays at two
//          decimals, trailing zeros trimmed, and ALWAYS carries its unit) ·
//          BR-SHL-034 (every displayed date through one formatter)
// ───────────────────────────────────────────────────────
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY — CLAUDE.md hard-won law 7(2).**
//
//   · *"`On since` shows a date"* passes on the INSTALL date, which is the bug.
//     So the fixtures below give `install_date` and `assigned_from` DIFFERENT
//     days and every case asserts which one reached the cell — and one case
//     carries an `install_date` with NO `assigned_from`, where the old code
//     rendered a date and the correct answer is the dash.
//   · *"`Last read` shows a number"* passes on the usage figure it already
//     showed. So every case asserts the READING, digit for digit, and the
//     first-read case asserts the usage clause is ABSENT rather than zero.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { AssetRow, UnitRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import i18n from "@/i18n";

import { UnitAssetsTab } from "./UnitDetailPage";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** The real beta's own numbers, so the assertions below are not invented:
 *  `W-5042` on `brazosbend` holds four reads, the newest
 *  `current_value=2585.000000 / consumption=10.000000 kgal` on 2026-08-11 and
 *  the earliest `current_value=2554.000000 / consumption=None` — the first
 *  read, which is the PO's reported case. Measured 2026-09-19. */
const READING = "2585.000000";
const USAGE = "10.000000";

function unit(meters: UnitRow["meters"]): UnitRow {
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
    services: ["electric", "water"],
    meters,
    occupancy: "occupied",
    occupant: "Miller, Sarah",
    account_no: "A-00412",
    status: "active",
    metered_services: [],
    sub_metered: false,
  };
}

function meterRef(assetNo: string, id: string) {
  return { id, asset_no: assetNo, qualifier: null, category: "meters" };
}

/** One registry row for a meter standing ON the unit. */
function onUnit(overrides: Partial<AssetRow> = {}): AssetRow {
  return {
    id: "a-5042",
    asset_no: "W-5042",
    serial_no: null,
    type: "meter",
    type_name: "Meter",
    tab: "meters",
    status: "active",
    status_name: "Installed",
    behavior_class: "in_service",
    meter_type: "walk_by",
    meter_type_name: "walk-by",
    read_method: "walk_by",
    read_method_name: "walk-by",
    multiplier: "1",
    size_class: '5/8"',
    // The size AS A CLERK READS IT, beside the code (`DEF-AST-7130`).
    size_class_name: null,
    unit: "kgal",
    net_metering: false,
    manufacturer: "Badger Meter",
    model: null,
    // ⚠ **DELIBERATELY A DIFFERENT DAY FROM `assigned_from` BELOW.** If the two
    // agreed, a cell reading either field would pass every case in this file.
    install_date: "2023-05-02",
    parent_asset_no: null,
    service_point_id: "sp-1",
    assigned_unit_id: "u-101a",
    assigned_from: "2026-06-14",
    assigned_to: "Unit A",
    assigned_address: "1408 Bluestem Ln",
    assigned: true,
    test_due: false,
    retire_date: null,
    retire_reason: null,
    replaced_by: null,
    actions: ["view", "edit", "reassign", "retire"],
    service: "water",
    last_read: {
      current_value: READING,
      consumption: USAGE,
      unit: "kgal",
      read_at: "2026-08-11",
    },
    ...overrides,
  };
}

function mountTab(rows: AssetRow[], meters = [meterRef("W-5042", "a-5042")]) {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      new Response(
        JSON.stringify({ count: rows.length, next: null, previous: null, results: rows }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/units/u-101a?tab=assets`]}>
          <Routes>
            <Route
              path="/:tenant/premises/units/:unitId"
              element={
                <UnitAssetsTab
                  unit={unit(meters)}
                  client={client}
                  t={t}
                  regional={{ timeZone: "America/Chicago", dateFormat: "DD/MM/YYYY" }}
                  writeBlockedReason={null}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The one data row of the on-unit table. */
async function row() {
  const cell = await screen.findByText("W-5042");
  const tr = cell.closest("tr");
  if (tr === null) {
    throw new Error("the asset row did not render");
  }
  return tr;
}

afterEach(cleanup);

describe("`On since` is when it arrived HERE, not when it was installed (DEF-MET-5861)", () => {
  it("renders the assignment's from_date and NOT the install date", async () => {
    mountTab([onUnit()]);
    const tr = await row();
    // 14 June 2026 — the day it arrived on this unit.
    expect(within(tr).getByText("14/06/2026")).toBeInTheDocument();
    // ⚠ **THE RED PROOF.** 2 May 2023 is `install_date`, which is what this
    // column rendered before. Its presence anywhere in the row would mean the
    // cell is still reading the wrong field.
    expect(within(tr).queryByText("02/05/2023")).toBeNull();
  });

  it("a meter with an install date but no assignment date shows the dash", async () => {
    // The mirror of the reported defect, and the case a naive fix breaks: the
    // old cell rendered `install_date` here, which answers a question nobody
    // asked in a column headed `On since`.
    mountTab([onUnit({ assigned_from: null })]);
    const tr = await row();
    expect(within(tr).queryByText("02/05/2023")).toBeNull();
    expect(within(tr).queryByText("14/06/2026")).toBeNull();
  });

  it("the meter a clerk just assigned from stock shows TODAY, not a dash", async () => {
    // The PO's reported symptom, in its exact shape: a shelf spare carries no
    // `install_date` at all (`_validate_asset` requires one only when a unit is
    // given), so the old cell could only ever draw a dash on a freshly
    // assigned meter — which is what they saw.
    mountTab([onUnit({ install_date: null, assigned_from: "2026-09-19" })]);
    const tr = await row();
    expect(within(tr).getByText("19/09/2026")).toBeInTheDocument();
  });
});

describe("`Last read` shows the READING, with the usage beside it (DEF-MET-5862)", () => {
  it("a read with usage shows date · reading · usage", async () => {
    mountTab([onUnit()]);
    const tr = await row();
    const text = (tr.textContent ?? "").replace(/\s+/g, " ");
    // ⚠ **THE READING IS THE ASSERTION.** `2,585 kgal` is `current_value`
    // through `UnitCell` — BR-MET-144's two-decimal trim, grouped for reading,
    // and never the raw `2585.000000` that `DEF-1120` printed.
    expect(text).toContain("2,585 kgal");
    // The usage survives beside it, named, so two quantities in one cell
    // cannot be confused for each other.
    expect(text).toContain("10 kgal");
    expect(text).toContain("used");
    expect(within(tr).getByText("11/08/2026")).toBeInTheDocument();
  });

  it("A FIRST READ shows its date AND its reading — never a bare date", async () => {
    // ⚠ **THE PO's ACTUAL CASE.** A register's first read has no previous
    // value, so `consumption` is null — and the cell drew the date alone over
    // a reading that was visible on two other screens.
    mountTab([
      onUnit({
        last_read: {
          current_value: "2554.000000",
          consumption: null,
          unit: "kgal",
          read_at: "2026-05-27",
        },
      }),
    ]);
    const tr = await row();
    const text = (tr.textContent ?? "").replace(/\s+/g, " ");
    expect(within(tr).getByText("27/05/2026")).toBeInTheDocument();
    expect(text).toContain("2,554 kgal");
    // ⚠ **NO ZERO AND NO `used` CLAUSE.** `0 kgal used` would state that the
    // meter measured nothing, which is a different and false fact
    // (`BR-MET-106`, `DEF-079` — the quiet dash, never a zero).
    expect(text).not.toContain("used");
    expect(text).not.toContain("0 kgal");
  });

  it("an ESTIMATE — a usage with no reading — still draws its usage", async () => {
    // BR-MET-028's mirror case: nobody read the dial, so there is a
    // consumption and no `current_value`. The two clauses are independent
    // precisely so this row is not lost.
    mountTab([
      onUnit({
        last_read: {
          current_value: null,
          consumption: "9.500000",
          unit: "kgal",
          read_at: "2026-08-11",
        },
      }),
    ]);
    const tr = await row();
    const text = (tr.textContent ?? "").replace(/\s+/g, " ");
    expect(text).toContain("9.5 kgal");
    expect(text).toContain("used");
  });

  it("a meter with no committed read says so, and says nothing about a quantity", async () => {
    mountTab([onUnit({ last_read: null })]);
    const tr = await row();
    expect(within(tr).getByText("no read yet")).toBeInTheDocument();
    expect((tr.textContent ?? "")).not.toContain("kgal");
  });
});

describe("the two columns answer independently", () => {
  it("the rows are the server's page for the unit, never a row of dashes", async () => {
    // ⚠ **THIS CASE ASSERTED A ROW OF DASHES UNTIL `DEF-MET-8362`.** The unit
    // payload's `meters` were the SPINE and the PREMISES' first 200 registry
    // rows only added columns, so a meter the premises page did not reach kept
    // its row with every column '—' — which is exactly what the J71 walk
    // photographed on Unit B. The tab now asks `f.unit_id` for its own page,
    // so a seated asset always comes back WITH its registry row; a reference
    // the server did not return is not drawn as a row of absences.
    mountTab([], [meterRef("W-5042", "a-5042")]);
    await waitFor(() =>
      expect(screen.getByText(t("metering.units.assetsEmpty"))).toBeInTheDocument(),
    );
    expect(screen.queryByText("W-5042")).toBeNull();
  });
});

// packet: DEF-MET-5861 + DEF-MET-5862 (maintenance lane, PO ruling 2026-09-19)
// generated: 2026-09-19 by the unit-assets maintenance lane — both columns
//   were RED first against the shipped code: `On since` rendered 02/05/2023
//   (the install date) and `Last read` rendered a bare date on the first-read
//   case. Both failures were watched before either fix was written.
// ──────────────────────────────────────────────────────────
